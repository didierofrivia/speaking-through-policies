# Ian: Infrastructure Provider

![Ian](../images/ian-intro.png)

### Login to the cluster
```sh
aws eks update-kubeconfig --name speaking-through-policies --region eu-north-1
```

### Install cert-manager

```sh
helm repo add jetstack https://charts.jetstack.io --force-update
helm install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true
```

### Install AWS Load Balancer Controller

```sh
CLUSTER_NAME=speaking-through-policies
REGION=eu-north-1
ACCOUNT_ID=$(aws sts get-caller-identity \
  --query Account \
  --output text)
OIDC_PROVIDER=$(aws eks describe-cluster \
  --name $CLUSTER_NAME \
  --region $REGION \
  --query "cluster.identity.oidc.issuer" \
  --output text | sed -e "s/^https:\/\///")
VPC_ID=$(aws eks describe-cluster \
  --name $CLUSTER_NAME \
  --region $REGION \
  --query "cluster.resourcesVpcConfig.vpcId" \
  --output text)
SERVICE_ACCOUNT_NAMESPACE=kube-system
SERVICE_ACCOUNT_NAME=aws-load-balancer-controller
ROLE_NAME=AmazonEKSLoadBalancerControllerRole

OIDC_PROVIDER_HOST=$(echo $OIDC_PROVIDER | cut -d '/' -f1)
aws iam create-open-id-connect-provider \
  --url https://$OIDC_PROVIDER \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list $(openssl s_client -connect $OIDC_PROVIDER_HOST:443 -servername $OIDC_PROVIDER_HOST < /dev/null 2>/dev/null | openssl x509 -fingerprint -noout | cut -d= -f2 | sed 's/://g')

curl -o /tmp/iam-policy.json https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/main/docs/install/iam_policy.json
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file:///tmp/iam-policy.json

cat > /tmp/trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_PROVIDER}"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "${OIDC_PROVIDER}:sub": "system:serviceaccount:${SERVICE_ACCOUNT_NAMESPACE}:${SERVICE_ACCOUNT_NAME}"
        }
      }
    }
  ]
}
EOF
aws iam create-role \
  --role-name $ROLE_NAME \
  --assume-role-policy-document \
  file:///tmp/trust-policy.json

aws iam attach-role-policy \
  --role-name $ROLE_NAME \
  --policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy

kubectl create serviceaccount $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE
kubectl annotate serviceaccount $SERVICE_ACCOUNT_NAME -n $SERVICE_ACCOUNT_NAMESPACE \
  eks.amazonaws.com/role-arn=arn:aws:iam::${ACCOUNT_ID}:role/$ROLE_NAME

helm repo add eks https://aws.github.io/eks-charts && helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system \
  --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false \
  --set serviceAccount.name=$SERVICE_ACCOUNT_NAME \
  --set region=$REGION \
  --set vpcId=$VPC_ID
```

### Install Envoy Gateway (gateway controller)

```sh
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.3.1\
  --namespace envoy-gateway-system \
  --create-namespace

kubectl get configmap -n envoy-gateway-system envoy-gateway-config \
  -o jsonpath='{.data.envoy-gateway\.yaml}' > /tmp/envoy-gateway.yaml
yq e '.extensionApis.enableEnvoyPatchPolicy = true' -i /tmp/envoy-gateway.yaml
kubectl create configmap -n envoy-gateway-system envoy-gateway-config \
  --from-file=envoy-gateway.yaml=/tmp/envoy-gateway.yaml -o yaml --dry-run=client | kubectl replace -f -
kubectl rollout restart deployment envoy-gateway -n envoy-gateway-system
rm -rf /tmp/envoy-gateway.yaml

kubectl apply -f -<<EOF
apiVersion: gateway.envoyproxy.io/v1alpha1
kind: EnvoyProxy
metadata:
  name: gatewayclass-config-aws-nlb-internal
  namespace: envoy-gateway-system
spec:
  provider:
    kubernetes:
      envoyService:
        annotations:
          service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
          service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    type: Kubernetes
---
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: eg
spec:
  controllerName: gateway.envoyproxy.io/gatewayclass-controller
  parametersRef:
    group: gateway.envoyproxy.io
    kind: EnvoyProxy
    name: gatewayclass-config-aws-nlb-internal
    namespace: envoy-gateway-system
EOF
```

### Install Kuadrant (policy controller)

```sh
helm repo add kuadrant https://kuadrant.io/helm-charts/ --force-update
helm install kuadrant-operator kuadrant/kuadrant-operator \
  --version 1.3.0-alpha1\
  --namespace kuadrant-system \
  --create-namespace \
  --wait

kubectl -n kuadrant-system patch deployment kuadrant-operator-controller-manager \
  --type='json' \
  -p='[{"op": "add", "path": "/spec/template/spec/containers/0/env/-", "value": {"name": "AUTH_SERVICE_TIMEOUT", "value": "5s"}}]'

kubectl create -n kuadrant-system -f - <<EOF
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
spec: {}
EOF
```

### Create an access for Chihiro

```sh
kubectl create serviceaccount chihiro -n kube-system
kubectl patch clusterrolebinding cluster-admin --type='json' -p='[{"op": "add", "path": "/subjects/-", "value": {"kind": "ServiceAccount", "name": "chihiro", "namespace": "kube-system"}}]'
```

Handover Chihiro's temporary access token:

```sh
kubectl create token chihiro -n kube-system --duration 8760h | pbcopy
```

<br/>
<br/>
<br/>

### Cleanup

```sh
kubectl delete namespace bakery-apps
kubectl delete namespace ingress-gateways
kubectl delete clusterissuer bakery-apps-ca
kubectl delete serviceaccount chihiro -n kube-system
```
