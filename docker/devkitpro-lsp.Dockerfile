FROM devkitpro/devkita64:20260219

RUN apt-get update -qq \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
       bear clangd-19 \
    && rm -rf /var/lib/apt/lists/*

USER 1000:1000
ENTRYPOINT ["clangd-19"]
