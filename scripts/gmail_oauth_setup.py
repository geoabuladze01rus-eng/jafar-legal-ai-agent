from __future__ import annotations

import argparse

from jafar.gmail_auth import (
    GmailCredentialStoreError,
    GmailReauthorizationRequired,
    GmailSetupRequired,
    KeychainGmailCredentialStore,
    authorize_gmail_desktop_app,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Authorize Jafar's local Gmail gateway with the exact gmail.readonly scope "
            "and store the credential bundle in the local protected keychain."
        )
    )
    parser.add_argument(
        "--client-secrets",
        required=True,
        help="path to the downloaded Google OAuth Desktop app JSON (never commit it)",
    )
    args = parser.parse_args()

    try:
        authorize_gmail_desktop_app(
            args.client_secrets,
            KeychainGmailCredentialStore(),
        )
    except (GmailSetupRequired, GmailReauthorizationRequired, GmailCredentialStoreError) as exc:
        print(f"GMAIL OAUTH SETUP: BLOCKED — {exc}")
        return 2

    print("GMAIL OAUTH SETUP: PASS")
    print("Разрешение ограничено gmail.readonly; токен сохранён только локально в Keychain.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
