FROM ubuntu:24.04

ARG RUNNER_VERSION=2.337.0
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       ca-certificates curl git jq python3 python3-pip python3-venv sudo \
       libicu74 libssl3 libkrb5-3 zlib1g liblttng-ust1t64 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3 /usr/local/bin/python \
    && useradd --create-home --shell /bin/bash runner

WORKDIR /runner
RUN curl --fail --location --silent --show-error \
      "https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz" \
      | tar -xz \
    && ./bin/installdependencies.sh \
    && chown -R runner:runner /runner

COPY entrypoint.sh /usr/local/bin/runner-entrypoint
RUN chmod 0755 /usr/local/bin/runner-entrypoint

USER runner
ENTRYPOINT ["/usr/local/bin/runner-entrypoint"]
