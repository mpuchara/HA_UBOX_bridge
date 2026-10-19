ARG BUILD_VERSION=0.3.0
ARG BUILD_ARCH=amd64
FROM ghcr.io/home-assistant/base:3.24
ARG BUILD_VERSION
ARG BUILD_ARCH
ARG UBOX_P4P_COMMIT=6f9f87fc31da4eb86531a81b08b3b1ffa4db5fa8
LABEL io.hass.version="${BUILD_VERSION}" io.hass.type="app" io.hass.arch="${BUILD_ARCH}"
RUN apk add --no-cache python3 py3-pip ffmpeg git ca-certificates build-base python3-dev linux-headers \
    && python3 -m venv /opt/ubox-venv \
    && git clone --filter=blob:none --no-checkout https://github.com/mahumadad/ubox-p4p.git /opt/ubox-p4p \
    && git -C /opt/ubox-p4p fetch --depth 1 origin "$UBOX_P4P_COMMIT" \
    && git -C /opt/ubox-p4p checkout --detach FETCH_HEAD \
    && /opt/ubox-venv/bin/pip install --no-cache-dir -r /opt/ubox-p4p/requirements.txt \
    && apk del build-base python3-dev linux-headers git
COPY bridge.py cloud_api.py /app/
COPY run.sh /run.sh
RUN chmod 0755 /run.sh && python3 -m py_compile /app/bridge.py /app/cloud_api.py
EXPOSE 8099 8100
CMD ["/run.sh"]
