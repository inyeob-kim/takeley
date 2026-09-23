/// API base URL for TAKELEY FastAPI backend.
const String kApiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://127.0.0.1:8000',
);

/// Public share origin (landing). Defaults to API host.
const String kShareOrigin = String.fromEnvironment(
  'SHARE_ORIGIN',
  defaultValue: 'http://127.0.0.1:8000',
);

const String kAppVersion = String.fromEnvironment(
  'APP_VERSION',
  defaultValue: '1.0.0',
);

String get kPrivacyUrl => '${kShareOrigin.replaceAll(RegExp(r'/$'), '')}/privacy';

String get kSupportUrl => '${kShareOrigin.replaceAll(RegExp(r'/$'), '')}/support';
