# Run VerboFlex locally

Use a dedicated checkout with Docker and the Compose plugin. The base Compose
file is a development definition: it is not suitable for direct public exposure.
It expects provider configuration, and secure cookies require HTTPS outside
browser loopback exceptions.

For a complete HTTPS installation with generated secrets, migrations and the first
administrator, use the [demo deployment recipe](demo-deployment.md). That recipe
uses production settings and separate volumes, and can run with public GitHub
sample data without connecting a Bitbucket account.

For application development and disposable test infrastructure, follow
[Application checks](application-ci.md). For the static product website:

```sh
python3 site/build.py
python3 site/check.py
python3 -m http.server 4174 --bind 127.0.0.1 --directory site/dist
```

Environment files, provider credentials, TLS private keys and database backups
belong outside version control. Keep the encryption keyring with the corresponding
private backup. See [backup and restore](backup-restore.md) and
[MCP setup](../mcp-server/README.md).
