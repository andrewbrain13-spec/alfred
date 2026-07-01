# Microsoft Graph setup (recommended for Microsoft 365)

The Graph source reads your mailbox over outbound HTTPS only — no IMAP, no
public webhook endpoint. It needs a one-time app registration in Entra ID
(Azure AD). On a work tenant you may need an IT admin to approve this.

## 1. Register an application

1. Go to https://portal.azure.com → **Microsoft Entra ID** → **App registrations**
   → **New registration**.
2. Name: `Alfred`. Supported account types: **Single tenant**.
3. After creation, note the **Application (client) ID** and **Directory (tenant) ID**.

## 2. Choose an auth mode

### Option A — Delegated (device code), for your own mailbox

Best for an always-on personal machine: you sign in once, and a refresh token
is cached locally.

1. In the app → **Authentication** → **Add a platform** → **Mobile and desktop
   applications**, and enable **Allow public client flows** (set the toggle to
   "Yes" under Advanced settings).
2. **API permissions** → **Add a permission** → **Microsoft Graph** →
   **Delegated permissions** → add **Mail.Read** (and **Mail.Send** if you use
   the reply workflow via Graph later). Grant admin consent if required.
3. Config:

   ```yaml
   source:
     type: graph
     name: outlook
     tenant_id: ${ALFRED_TENANT_ID}
     client_id: ${ALFRED_CLIENT_ID}
     auth: device_code
     folder: inbox
   ```

On first run Alfred prints a URL and a code — visit it once to authenticate.

### Option B — App-only (client credentials), for an unattended service account

1. **API permissions** → **Application permissions** → **Mail.Read**, then
   **Grant admin consent** (required).
2. **Certificates & secrets** → **New client secret**; copy the value.
3. Config:

   ```yaml
   source:
     type: graph
     name: outlook
     tenant_id: ${ALFRED_TENANT_ID}
     client_id: ${ALFRED_CLIENT_ID}
     client_secret: ${ALFRED_CLIENT_SECRET}
     auth: client_credentials
     folder: inbox
   ```

   Note: app-only reads a *specific* mailbox — scope it with an application
   access policy in Exchange, and target the mailbox via the Graph
   `/users/{id}` endpoint (adjust `_GRAPH` usage in `graph_source.py` if you go
   this route for a shared mailbox).

## 3. Install the dependency

```bat
.venv\Scripts\pip install msal
```

## 4. Set env vars and run

```bat
setx ALFRED_TENANT_ID "your-tenant-id"
setx ALFRED_CLIENT_ID "your-client-id"
setx ALFRED_CLIENT_SECRET "your-secret"   # only for client_credentials
```

Then validate as usual:

```bat
.venv\Scripts\python run.py --config config\rules.yaml --once
```
