ARG BUILD_VERSION=0.5.2
ARG BUILD_ARCH=amd64
FROM ghcr.io/home-assistant/base:3.24
ARG BUILD_VERSION
ARG BUILD_ARCH
ARG UBOX_WEB_COMMIT=c7787ec0c53b488797336799d9518bb3906d6d03
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
RUN apk add --no-cache python3 ffmpeg git ca-certificates build-base nodejs npm \
    && git clone --filter=blob:none --no-checkout https://github.com/asyrk/ubox-web.git /opt/ubox-web \
    && git -C /opt/ubox-web fetch --depth 1 origin "$UBOX_WEB_COMMIT" \
    && git -C /opt/ubox-web checkout --detach FETCH_HEAD \
    && cd /opt/ubox-web && npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && apk del build-base git
COPY bridge.py frame_quality.py cloud_api.py capture_live.js /app/
COPY run.sh /run.sh
RUN node --check /app/capture_live.js \
    && node /app/capture_live.js --self-test \
    && node -e "require('/opt/ubox-web/ubox-live-stream.js')" \
    && chmod 0755 /run.sh && python3 -m py_compile /app/bridge.py /app/frame_quality.py /app/cloud_api.py
EXPOSE 8099 8100
CMD ["/run.sh"]
