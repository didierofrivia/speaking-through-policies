# 👩🏻‍💻 Ana

> － _Hi, my name is Ana. I work with Chiriro at Evil Genius Cupcakes, where I am an **App Developer**._
> _My team writes, deploys and maintains software on Kubernetes, that the employees of our company use to operate the production of cupcakes._

> － _Recently, I worked on the latest version of our `baker` service, which is ready to be deployed to staging._

### Login to the cluster

```sh
kubectl config set-credentials ana --token=$ANA_TOKEN
kubectl config set-context ana --cluster=kind-evil-genius-cupcakes --user=ana --namespace=bakery-apps
alias kubectl="kubectl --context=ana"
```

### Deploy the baker app

```sh
kubectl apply -n bakery-apps -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: baker
spec:
  selector:
    matchLabels:
      app: baker
  template:
    metadata:
      labels:
        app: baker
    spec:
      containers:
      - name: backend
        image: quay.io/kuadrant/authorino-examples:talker-api
        imagePullPolicy: Always
        env:
        - name: PORT
          value: "3000"
        ports:
        - containerPort: 3000
        tty: true
  replicas: 1
---
apiVersion: v1
kind: Service
metadata:
  name: baker
spec:
  selector:
    app: baker
  ports:
    - port: 3000
      protocol: TCP
EOF
```

### Test the baker app within the cluster

```sh
kubectl run curl -n bakery-apps --attach --rm --restart=Never -q --image=curlimages/curl -- http://baker:3000 -s
```

### Check status of the gateway

```sh
kubectl get gateway/bakery-apps -n ingress-gateways -o jsonpath='{.status.conditions[?(.type=="Programmed")].status}'
# True%
```

### Attach a route to the gateway

```sh
kubectl apply -n bakery-apps -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: baker-route
spec:
  parentRefs:
  - kind: Gateway
    name: bakery-apps
    namespace: ingress-gateways
  rules:
  - matches:
    - path:
        value: /baker
    backendRefs:
    - kind: Service
      name: baker
      port: 3000
EOF
```

### Check the status of the route affected by a DNSPolicy

```sh
kubectl get httproute/baker-route -n bakery-apps \
  -o jsonpath='{.status.parents[?(.controllerName=="kuadrant.io/policy-controller")]}' | jq

# {
#   "conditions": [
#     {
#       "lastTransitionTime": "2025-03-19T11:35:43Z",
#       "message": "Object affected by DNSPolicy [ingress-gateways/bakery-dns]",
#       "observedGeneration": 1,
#       "reason": "Accepted",
#       "status": "True",
#       "type": "kuadrant.io/DNSPolicyAffected"
#     }
#   ],
#   "controllerName": "kuadrant.io/policy-controller", …
# }
```

### Test the baker app through the gateweay

```sh
curl http://cupcakes.demos.kuadrant.io/baker
```

### Test the baker app after TLS configured

```sh
curl http://cupcakes.demos.kuadrant.io/baker
# curl: (7) Failed to connect to cupcakes.demos.kuadrant.io port 80 after 7116 ms: Couldn't connect to server
```

### Check the status of the route affected by a TLSPolicy

```sh
kubectl get httproute/baker-route -n bakery-apps \
  -o jsonpath='{.status.parents[?(.controllerName=="kuadrant.io/policy-controller")]}' | jq

# {
#   "conditions": [
#     {
#       "lastTransitionTime": "2025-03-19T10:44:19Z",
#       "message": "Object affected by TLSPolicy [ingress-gateways/bakery-tls]",
#       "observedGeneration": 1,
#       "reason": "Accepted",
#       "status": "True",
#       "type": "kuadrant.io/TLSPolicyAffected"
#     }, …
#   ],
#   "controllerName": "kuadrant.io/policy-controller", …
# }
```

### Test the baker app hitting the HTTPS endpoint

```sh
curl https://cupcakes.demos.kuadrant.io/baker
# curl: (60) SSL certificate problem: unable to get local issuer certificate
# More details here: https://curl.se/docs/sslcerts.html
#
# curl failed to verify the legitimacy of the server and therefore could not
# establish a secure connection to it. To learn more about this situation and
# how to fix it, please visit the web page mentioned above.
```

### Bypass self-signed certificate verification by the client

```sh
curl https://cupcakes.demos.kuadrant.io/baker --insecure
# 200
```

### Test the baker app behind the deny-all default auth policy

```sh
curl https://cupcakes.demos.kuadrant.io/baker --insecure
# {
#   "error": "Forbidden",
#   "message": "Access denied by default by the gateway operator. If you are the administrator of the service, create a specific auth policy for the route."
# }
```

### Check the status of the route affected by an AuthPolicy

```sh
kubectl get httproute/baker-route -n bakery-apps \
  -o jsonpath='{.status.parents[?(.controllerName=="kuadrant.io/policy-controller")]}' | jq

# {
#   "conditions": [
#     {
#       "lastTransitionTime": "2025-03-19T10:46:26Z",
#       "message": "Object affected by AuthPolicy [ingress-gateways/deny-all]",
#       "observedGeneration": 1,
#       "reason": "Accepted",
#       "status": "True",
#       "type": "kuadrant.io/AuthPolicyAffected"
#     }, …
#   ],
#   "controllerName": "kuadrant.io/policy-controller", …
# }
```

### Define an AuthPolicy to replace the default deny-all one

```sh
kubectl apply -n bakery-apps -f -<<EOF
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: baker-auth
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: baker-route
  rules:
    authentication:
      north-south: # external users
        jwt:
          issuerUrl: https://gitlab.com
        priority: 1
      east-west: # other pods inside the cluster
        kubernetesTokenReview:
          audiences:
          - https://kubernetes.default.svc.cluster.local
        priority: 0
    authorization:
      external-users:
        when:
        - predicate: auth.identity.iss == "https://gitlab.com"
        patternMatching:
          patterns:
          - predicate: '"evil-genius-cupcakes" in auth.identity.groups_direct && request.method == "GET"'
      pods:
        when:
        - predicate: auth.identity.iss == "https://kubernetes.default.svc.cluster.local"
        patternMatching:
          patterns:
          - predicate: auth.identity["kubernetes.io"].namespace == "bakery-apps"
    response:
      unauthenticated:
        code: 302
        headers:
          location:
            value: https://gitlab.com/oauth/authorize?client_id=c0b3a4e52c5e60ccb40ccf7c9bd63828476cde4b71910beb463897069ce1ae29&redirect_uri=http://localhost/auth/callback&response_type=code&scope=openid
EOF
```

### Test the baker app impersonating an external user

#### Send a unauthenticated request to the baker app

```sh
curl https://cupcakes.demos.kuadrant.io/baker --insecure -i
# HTTP/2 302
# location: https://gitlab.com/oauth/authorize?client_id=c0b3a4e52c5e60ccb40ccf7c9bd63828476cde4b71910beb463897069ce1ae29&redirect_uri=http://localhost/auth/callback&response_type=code&scope=openid
```

Follow the redirect.

_(The browser will redirect to GitLab's login page.)_

Log in as a GitLab user who is a member of the 'evil-genius-cupcakes' group.

_(GitLab will redirect to a non-implemented web page containing an authorization &lt;code&gt;.)_

Copy the code.

#### Exchange the authorization code for an OIDC ID Token

```sh
export EXTERNAL_USER_TOKEN=$(curl -X POST -s \
  -d 'code=<code>' \
  -d 'redirect_uri=http://localhost/auth/callback' \
  -d 'client_id=c0b3a4e52c5e60ccb40ccf7c9bd63828476cde4b71910beb463897069ce1ae29' \
  -d 'grant_type=authorization_code' \
  https://gitlab.com/oauth/token | jq -r '.id_token')
```

#### Send an authenticated request to the baker app

```sh
curl -H "Authorization: Bearer $EXTERNAL_USER_TOKEN" https://cupcakes.demos.kuadrant.io/baker --insecure
# 200
```

#### Send a forbidden request to the baker app

```sh
curl -H "Authorization: Bearer $EXTERNAL_USER_TOKEN" https://cupcakes.demos.kuadrant.io/baker --insecure -X POST -i
# 403
```

### Test the baker app impersonating another pod running within the cluster

#### Create a Service Account to identify another pod 'portioning'

```sh
kubectl apply -n bakery-apps -f -<<EOF
apiVersion: v1
kind: ServiceAccount
metadata:
  name: portioning
EOF
```

#### Send an authenticated request to the baker app

```sh
export POD_SA_TOKEN=$(kubectl create token portioning)
curl -H "Authorization: Bearer $POD_SA_TOKEN" https://cupcakes.demos.kuadrant.io/baker --insecure
# 200
```

### Define a Rate Limit Policy for the baker app for a maximum of 5rp10s

```sh
kubectl apply -n bakery-apps  -f -<<EOF
apiVersion: kuadrant.io/v1
kind: RateLimitPolicy
metadata:
  name: baker-rate-limit
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: baker-route
  limits:
    global:
      rates:
      - limit: 5
        window: 10s
EOF
```

### Check the status of the route affected by a RateLimitPolicy

```sh
kubectl get httproute/baker-route -n bakery-apps \
  -o jsonpath='{.status.parents[?(.controllerName=="kuadrant.io/policy-controller")]}' | jq

# {
#   "conditions": [
#     {
#       "lastTransitionTime": "2025-03-19T10:51:48Z",
#       "message": "Object affected by RateLimitPolicy [bakery-apps/baker-rate-limit]",
#       "observedGeneration": 1,
#       "reason": "Accepted",
#       "status": "True",
#       "type": "kuadrant.io/RateLimitPolicyAffected"
#     }, …
#   ],
#   "controllerName": "kuadrant.io/policy-controller", …
# }
```

### Send a few requests to the baker app

```sh
while :; do curl -H "Authorization: Bearer $POD_SA_TOKEN" https://cupcakes.demos.kuadrant.io/baker --insecure -s --output /dev/null --write-out '%{http_code}\n' | grep -E --color "\b(429)\b|$"; sleep 1; done
# 200
# 200
# 200
# 200
# 200
# 429
# 429
# 429
# 429
# 429
# 200
# 200
```

### Check the status of the route affected by another RateLimitPolicy

```sh
kubectl get httproute/baker-route -n bakery-apps \
  -o jsonpath='{.status.parents[?(.controllerName=="kuadrant.io/policy-controller")]}' | jq

# {
#   "conditions": [
#     {
#       "lastTransitionTime": "2025-03-19T10:51:48Z",
#       "message": "Object affected by RateLimitPolicy [bakery-apps/baker-rate-limit ingress-gateways/gateway-rate-limit]",
#       "observedGeneration": 1,
#       "reason": "Accepted",
#       "status": "True",
#       "type": "kuadrant.io/RateLimitPolicyAffected"
#     }, …
#   ],
#   "controllerName": "kuadrant.io/policy-controller", …
# }
```

### Check the status of the baker RateLimitPolicy overridden by the more restrictive policy

```sh
kubectl get ratelimitpolicy/baker-rate-limit -n bakery-apps -o jsonpath='{.status.conditions[?(.type=="Enforced")]}' | jq
# {
#   "lastTransitionTime": "2025-03-19T11:09:17Z",
#   "message": "RateLimitPolicy is overridden by [ingress-gateways/gateway-rate-limit]",
#   "reason": "Overridden",
#   "status": "False",
#   "type": "Enforced"
# }
```

### Send a few requests to the baker app

```sh
while :; do curl -H "Authorization: Bearer $POD_SA_TOKEN" https://cupcakes.demos.kuadrant.io/baker --insecure -s --output /dev/null --write-out '%{http_code}\n' | grep -E --color "\b(429)\b|$"; sleep 1; done
# 200
# 200
# 429
# 429
# 429
# 429
# 429
# 429
# 429
# 429
# 200
# 200
```
