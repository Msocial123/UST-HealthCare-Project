{{- /* The service account's IAM role (IRSA) may only read this service's DB secret and the shared JWT key. */ -}}
{{- define "microservice.secretstore" -}}
apiVersion: external-secrets.io/v1
kind: SecretStore
metadata:
  name: {{ include "microservice.name" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
  annotations:
    argocd.argoproj.io/sync-wave: "-2"
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
spec:
  provider:
    aws:
      service: SecretsManager
      region: {{ required "secrets.awsRegion is required" .Values.secrets.awsRegion }}
      auth:
        jwt:
          serviceAccountRef:
            name: {{ include "microservice.name" . }}
{{- end -}}

{{- define "microservice.externalsecret" -}}
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: {{ include "microservice.secretName" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
  annotations:
    argocd.argoproj.io/sync-wave: "-2"
    argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
spec:
  refreshInterval: {{ .Values.secrets.refreshInterval }}
  secretStoreRef:
    name: {{ include "microservice.name" . }}
    kind: SecretStore
  target:
    name: {{ include "microservice.secretName" . }}
    creationPolicy: Owner
    template:
      engineVersion: v2
      data:
        DATABASE_URL: {{ `postgresql+psycopg://{{ .username }}:{{ .password }}@{{ .host }}:{{ .port }}/{{ .dbname }}?sslmode=require` | quote }}
        JWT_SECRET_KEY: {{ `{{ .key }}` | quote }}
        JWT_KEY_ID: {{ `{{ .kid }}` | quote }}
  dataFrom:
    - extract:
        key: {{ required "secrets.database is required" .Values.secrets.database }}
    - extract:
        key: {{ required "secrets.jwt is required" .Values.secrets.jwt }}
{{- end -}}
