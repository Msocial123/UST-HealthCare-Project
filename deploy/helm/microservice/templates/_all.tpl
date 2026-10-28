{{- /* Everything one microservice needs. Service charts render it with: {{ include "microservice.all" . }} */ -}}
{{- define "microservice.all" -}}
{{ include "microservice.serviceaccount" . }}
---
{{ include "microservice.configmap" . }}
---
{{ include "microservice.secretstore" . }}
---
{{ include "microservice.externalsecret" . }}
{{- if .Values.migrations.enabled }}
---
{{ include "microservice.migrationjob" . }}
{{- end }}
---
{{ include "microservice.deployment" . }}
---
{{ include "microservice.service" . }}
{{- end -}}
