{{- define "microservice.configmap" -}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "microservice.name" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
  annotations:
    argocd.argoproj.io/sync-wave: "-3"
data:
  PORT: {{ .Values.containerPort | quote }}
  {{- range $k, $v := mergeOverwrite (dict) .Values.env .Values.extraEnv }}
  {{ $k }}: {{ $v | toString | quote }}
  {{- end }}
{{- end -}}
