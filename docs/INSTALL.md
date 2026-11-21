# Install guide

For one client factory. Hardware and what the client must prepare are in [DEPLOYMENT_REQUIREMENTS.md](DEPLOYMENT_REQUIREMENTS.md). This guide starts with a Linux server that has Docker and Docker Compose v2.

Every command below was run as written during development, except the ones that need a real domain or a real camera. The "Not tested" notes say which.

## 1. Get the code

```bash
git clone https://github.com/pbs002-s/swingai.git stitchsense
cd stitchsense
```

## 2. Create the settings file

```bash
deploy/scripts/init-env.sh stitchsense.your-factory.example admin@your-factory.example
```

- The first argument is the address people will type. A real domain gets an HTTPS certificate automatically. For a trial on one machine use `localhost`.
- The script prints the admin password once. Save it in your password manager.
- It refuses to overwrite an existing `deploy/.env`. Replacing it would change `SS_SECRETS_KEY` and make every saved camera password unreadable.
- Add `demo` as a third argument for a demo install (university or sales). It creates demo logins and a simulated factory. Never use it for a real factory.

Back up `deploy/.env` somewhere safe, **separately from the database backups**.

## 3. Start

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

The API creates its tables and the first admin account on start. Open `https://<your address>` and log in with the admin email and password from step 2.

Not tested: automatic HTTPS needs a real domain that points at this server, with ports 80 and 443 open to the internet for the certificate check.

## 4. Check it is healthy

```bash
deploy/scripts/healthcheck.sh http://localhost
```

Put it in cron every 5 minutes so you hear about problems before the factory does:

```cron
*/5 * * * *  /opt/stitchsense/deploy/scripts/healthcheck.sh http://localhost || echo "StitchSense unhealthy" | mail -s alert you@example.com
```

## 5. Set up the factory

Log in as the admin, then in this order:

1. **Setup**: factory structure (floors, lines, stations), machine types and brands, operations with SMV, workers. CSV templates for each are in [IMPORT_TEMPLATES.md](IMPORT_TEMPLATES.md).
2. **Policies**: shift times and breaks, thresholds, data retention. Each save is a new version.
3. **Users**: one login per person, each with the role they need. Roles and what they can see are in [PRD.md](PRD.md) section 5.
4. **Settings**: review the alert rules and use **Test 7 days** before changing a threshold.

## 6. Backups (do this before the factory goes live)

```bash
# every night at 02:00, keeping 14 days
0 2 * * *  /opt/stitchsense/deploy/scripts/backup.sh /var/backups/stitchsense
```

**Prove the backup works** right after the first one, then once a month:

```bash
deploy/scripts/restore.sh --verify /var/backups/stitchsense/stitchsense-<stamp>.dump
```

This restores into a scratch database, checks the key tables have rows, and removes it. It touches nothing live.

To recover after a disaster (this replaces the live database with the backup; everything written since is lost):

```bash
deploy/scripts/restore.sh --replace /var/backups/stitchsense/stitchsense-<stamp>.dump
```

You also need the original `deploy/.env` (it holds `SS_SECRETS_KEY`). Copy the dumps off the server regularly; a backup on the same disk does not survive the disk.

## 7. Cameras (release 3)

On the floor, on the edge box:

```bash
cd edge
cp .env.example .env     # set SS_API_URL, SS_DEVICE_TOKEN, MQTT_PASSWORD, GO2RTC_PASSWORD
docker compose up -d
```

Then in the web app: Cameras, **Add camera** (the wizard finds the camera, tests it, and lets you draw privacy zones). Details and the phone-camera test setup are in [edge/README.md](../edge/README.md).

- **Draw privacy zones for every camera before enabling live view.** They are painted black on the edge box before the picture is shown. A camera with no zone is shown in full, and the live wall labels it "No privacy mask".
- Live view works only on the factory network. Do not forward ports 1984 or 8555.
- Show the worker notice ([WORKER_PRIVACY_NOTICE_TEMPLATE.md](WORKER_PRIVACY_NOTICE_TEMPLATE.md)) before cameras go live.

Not tested: live view with real cameras (it was tested with simulated feeds and a browser camera only).

## 8. Updating

```bash
deploy/scripts/backup.sh /var/backups/stitchsense      # always first
git pull
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

The API applies database changes on start. If it does not come up healthy, check `docker compose -f deploy/docker-compose.yml logs api`; every log line carries a request ID, and responses return it in the `X-Request-ID` header, so a complaint can be matched to its log lines.

## What a new person should expect to find

- **Login fails with "too many attempts":** accounts lock after repeated wrong passwords; wait or ask another admin.
- **An old backup will not restore:** run `--verify` on a newer one, and check the dump is not truncated (`backup.sh` refuses to keep an unreadable dump).
- **Data is disappearing:** the retention policy (Policies page) deletes raw events and audit rows past their age, every few hours. It records each purge in the audit log.
