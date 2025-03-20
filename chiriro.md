# Chiriro: Cluster Operator

![Chiriro](images/chiriro-intro.png)

### Login in to the cluster

```sh
kubectl config set-credentials chiriro --token=$CHIRIRO_TOKEN
kubectl config set-context chiriro --cluster=kind-evil-genius-cupcakes --user=chiriro --namespace=default
alias kubectl="kubectl --context=chiriro"
```

### Create the apps namespace

```sh
kubectl create namespace bakery-apps
```

### Create an access for Ana

```sh
kubectl create -n bakery-apps -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: bakery-dev-role
rules:
- apiGroups:
  - '*'
  resources:
  - '*'
  verbs:
  - '*'
EOF

kubectl create serviceaccount ana -n bakery-apps
kubectl create rolebinding bakery-dev-role-binding \
  --role=bakery-dev-role --serviceaccount=bakery-apps:ana -n bakery-apps
```

```sh
ANA_TOKEN=$(kubectl create token ana -n bakery-apps --duration 8760h)
```

<br/>
<br/>
<br/>

### Define a gateway

```sh
kubectl create namespace ingress-gateways

kubectl apply -n ingress-gateways -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: bakery-apps
spec:
  gatewayClassName: eg
  listeners:
  - allowedRoutes:
      namespaces:
        from: Selector
        selector:
          matchLabels:
            apps: external
    name: http
    hostname: cupcakes.demos.kuadrant.io
    port: 80
    protocol: HTTP
EOF

kubectl label namespace/bakery-apps apps=external
```

Create a DNSPolicy:

```sh
kubectl -n ingress-gateways create secret generic aws-credentials \
  --type=kuadrant.io/aws \
  --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY

kubectl create -n ingress-gateways -f -<<EOF
apiVersion: kuadrant.io/v1
kind: DNSPolicy
metadata:
  name: bakery-dns
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: bakery-apps
  providerRefs:
  - name: aws-credentials
EOF
```

<br/>
<br/>
<br/>

### Grant permission for Ana to read gateway and gateway status

```sh
kubectl create -n ingress-gateways -f - <<EOF
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: bakery-dev-role
rules:
- apiGroups:
  - gateway.networking.k8s.io
  resources:
  - gateways
  - gateways/status
  verbs:
  - get
EOF

kubectl create rolebinding bakery-dev-role-binding --role=bakery-dev-role --serviceaccount=bakery-apps:ana -n ingress-gateways
```

<br/>
<br/>
<br/>

### Force all traffic in the `bakery-apps` namespace to go through the gateway

```sh
kubectl create -n bakery-apps -f - <<EOF
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: gateway-traffic-only
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: envoy-gateway-system
          podSelector:
            matchLabels:
              app.kubernetes.io/component: proxy
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              name: envoy-gateway-system
          podSelector:
            matchLabels:
              app.kubernetes.io/component: proxy
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - port: 53
          protocol: UDP
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
EOF
```

### Enable TLS on the gateway with automatic certificate management:

```sh
kubectl apply -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: bakery-apps
  namespace: ingress-gateways
spec:
  gatewayClassName: eg
  listeners:
  - allowedRoutes:
      namespaces:
        from: Selector
        selector:
          matchLabels:
            apps: external
    name: https
    hostname: cupcakes.demos.kuadrant.io
    port: 443
    protocol: HTTPS
    tls:
      mode: Terminate
      certificateRefs:
      - name: ingress-gateway-cert
        kind: Secret
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: bakery-apps-ca
spec:
  selfSigned: {}
---
apiVersion: kuadrant.io/v1
kind: TLSPolicy
metadata:
  name: bakery-tls
  namespace: ingress-gateways
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: bakery-apps
  issuerRef:
    group: cert-manager.io
    kind: ClusterIssuer
    name: bakery-apps-ca
EOF
```

<br/>
<br/>
<br/>

### Define a default 'deny-all' auth policy for all routes attached to the gateway

```sh
kubectl apply -f - <<EOF
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: deny-all
  namespace: ingress-gateways
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: bakery-apps
  rules:
    authorization:
      deny-all:
        opa:
          rego: "allow = false"
    response:
      unauthorized:
        headers:
          "content-type":
            value: application/json
        body:
          value: |
            {
              "error": "Forbidden",
              "message": "Access denied by default by the gateway operator. If you are the administrator of the service, create a specific auth policy for the route."
            }
EOF
```

<br/>
<br/>
<br/>

### Define a Rate Limit Policy for all routes for a maximum of 2rp10s

```sh
kubectl apply -n ingress-gateways  -f -<<EOF
apiVersion: kuadrant.io/v1
kind: RateLimitPolicy
metadata:
  name: gateway-rate-limit
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: bakery-apps
  overrides:
    limits:
      global:
        rates:
        - limit: 2
          window: 10s
EOF
```

### Check the status of the RateLimitPolicy

```sh
kubectl get ratelimitpolicy/gateway-rate-limit -n ingress-gateways -o yaml | yq
```
