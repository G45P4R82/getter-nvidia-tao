# Ansible Deployment

This playbook deploys the official TAO FTMS Docker Compose bundle in an
isolated directory. It does not stop or reconfigure other Compose projects.

## Prepare Vault

```bash
cp ansible/inventory/group_vars/vault.yml.example ansible/inventory/group_vars/vault.yml
ansible-vault encrypt ansible/inventory/group_vars/vault.yml
```

Set `tao_ftms_ngc_api_key` in the unencrypted file before encrypting it. Do not
commit `vault.yml`.

## Check only

The default variables keep `tao_ftms_start` disabled:

```bash
SSHPASS='SSH_PASSWORD' ansible-playbook --ask-pass --ask-vault-pass \
  ansible/playbooks/deploy.yml --check
```

## Install and validate, without starting FTMS

```bash
SSHPASS='SSH_PASSWORD' ansible-playbook --ask-pass --ask-vault-pass \
  ansible/playbooks/deploy.yml
```

## Start FTMS

Set `tao_ftms_start: true` in `ansible/group_vars/production.yml` only after
the check and rendered Compose configuration have been reviewed, then run the
playbook again. The role invokes only the TAO wrapper in
`/home/getter/tao-ftms`.

## Safety boundaries

- No `docker compose down` is executed.
- No Docker prune command is executed.
- Existing Compose projects are not discovered as deployment targets.
- TAO ports are separate from the ports found on the host.
- The FTMS official bundle requires Docker socket access for TAO job launch;
  review this trust boundary before allowing untrusted API users.
