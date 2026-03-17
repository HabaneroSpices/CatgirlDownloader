FROM debian:12

ARG NFPM_VERSION=2.43.2
ARG APPIMAGETOOL_URL=https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    git \
    xz-utils \
    file \
    flatpak-builder \
    meson \
    ninja-build \
    pkg-config \
    gettext \
    desktop-file-utils \
    appstream-util \
    appstream \
    gtk-update-icon-cache \
    libglib2.0-bin \
    libglib2.0-dev-bin \
    libglib2.0-dev \
    python3 \
    python3-gi \
    python3-requests \
    && rm -rf /var/lib/apt/lists/*

RUN set -eux; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) nfpm_arch="x86_64" ;; \
      arm64) nfpm_arch="arm64" ;; \
      *) echo "Unsupported architecture for nfpm: $arch"; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/nfpm.tar.gz "https://github.com/goreleaser/nfpm/releases/download/v${NFPM_VERSION}/nfpm_${NFPM_VERSION}_Linux_${nfpm_arch}.tar.gz"; \
    tar -C /usr/local/bin -xzf /tmp/nfpm.tar.gz nfpm; \
    chmod +x /usr/local/bin/nfpm; \
    rm -f /tmp/nfpm.tar.gz

RUN curl -fsSL -o /opt/appimagetool.AppImage "$APPIMAGETOOL_URL" \
    && chmod +x /opt/appimagetool.AppImage \
    && printf '%s\n' '#!/bin/sh' 'exec /opt/appimagetool.AppImage --appimage-extract-and-run "$@"' > /usr/local/bin/appimagetool \
    && chmod +x /usr/local/bin/appimagetool

WORKDIR /workspace
CMD ["sh", "./package.sh"]
