{{- define "microservice.name" -}}
{{- required "name is required" .Values.name -}}
{{- end -}}

{{- define "microservice.labels" -}}
app.kubernetes.io/name: {{ include "microservice.name" . }}
app.kubernetes.io/part-of: smart-hospital
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
{{- include "microservice.datadogLabels" . | nindent 0 }}
{{- end -}}

{{- define "microservice.selectorLabels" -}}
app.kubernetes.io/name: {{ include "microservice.name" . }}
{{- end -}}

{{- define "microservice.image" -}}
{{- printf "%s:%s" (required "image.repository is required" .Values.image.repository) (required "image.tag is required (set it in dev-values.yaml)" .Values.image.tag) -}}
{{- end -}}

{{- define "microservice.secretName" -}}
{{- printf "%s-env" (include "microservice.name" .) -}}
{{- end -}}

{{- define "microservice.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "microservice.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{- define "microservice.envFrom" -}}
- configMapRef:
    name: {{ include "microservice.name" . }}
- secretRef:
    name: {{ include "microservice.secretName" . }}
{{- end -}}

{{- /* Datadog unified service tagging (env/service/version), set when datadog.env is configured. */ -}}
{{- define "microservice.datadogLabels" -}}
{{- with (.Values.datadog | default dict).env }}
tags.datadoghq.com/env: {{ . | quote }}
tags.datadoghq.com/service: {{ include "microservice.name" $ }}
tags.datadoghq.com/version: {{ $.Values.image.tag | quote }}
{{- end }}
{{- end -}}
