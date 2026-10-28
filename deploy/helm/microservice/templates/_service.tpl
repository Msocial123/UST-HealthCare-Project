{{- /* NodePort: the Terraform ALB target group for this service forwards to this node port on every worker. */ -}}
{{- define "microservice.service" -}}
apiVersion: v1
kind: Service
metadata:
  name: {{ include "microservice.name" . }}
  labels:
    {{- include "microservice.labels" . | nindent 4 }}
spec:
  type: NodePort
  selector:
    {{- include "microservice.selectorLabels" . | nindent 4 }}
  ports:
    - name: http
      port: {{ .Values.containerPort }}
      targetPort: http
      nodePort: {{ required "service.nodePort is required" .Values.service.nodePort }}
      protocol: TCP
{{- end -}}
