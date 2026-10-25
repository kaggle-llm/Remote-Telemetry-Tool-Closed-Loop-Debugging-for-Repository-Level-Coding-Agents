"""Generate local secrets for the telemetry prototype without writing files."""

import secrets


def main():
    print("APP_SESSION_SECRET=" + secrets.token_urlsafe(48))
    print()
    print("User ingest keys are created in the Google-authenticated dashboard, not by this script.")
    print("A VITE_TELEMETRY_INGEST_KEY is public/extractable; never put developer or Supabase keys in the client bundle.")


if __name__ == "__main__":
    main()
