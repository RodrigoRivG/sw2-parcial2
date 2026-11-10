FROM docker.n8n.io/n8nio/n8n:2.46.6
COPY --chown=node:node iniciar.sh preparar.js /opt/agro/
COPY --chown=node:node flujos /opt/agro/flujos
USER node
ENTRYPOINT ["sh", "/opt/agro/iniciar.sh"]
