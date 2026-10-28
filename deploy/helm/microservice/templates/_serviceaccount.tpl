{{- define "microservice.serviceaccount" -}}
apiVersion: v1
kind: ServiceAccount
metadata:
  name: {{ include "microservice.name" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
  annotations:
    argocd.argoproj.io/sync-wave: "-3"
    {{- with .Values.serviceAccount.roleArn }}
    eks.amazonaws.com/role-arn: {{ . }}
    {{- end }}
automountServiceAccountToken: false
{{- end -}}
