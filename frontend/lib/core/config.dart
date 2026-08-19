/// Build-time configuration.
///
/// Values come from `--dart-define` so no key is ever baked into the source:
///
///   flutter run -d chrome \
///     --dart-define=API_BASE_URL=http://localhost:8000 \
///     --dart-define=API_KEY=...
library;

class AppConfig {
  const AppConfig({
    required this.baseUrl,
    required this.apiKey,
    this.timeout = const Duration(seconds: 45),
  });

  final String baseUrl;
  final String apiKey;
  final Duration timeout;

  static const AppConfig current = AppConfig(
    baseUrl: String.fromEnvironment(
      'API_BASE_URL',
      defaultValue: 'http://localhost:8000',
    ),
    apiKey: String.fromEnvironment('API_KEY', defaultValue: ''),
  );
}
