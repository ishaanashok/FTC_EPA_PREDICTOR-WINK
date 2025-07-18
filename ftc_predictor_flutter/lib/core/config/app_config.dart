class AppConfig {
  static const String appName = 'FTC Predictor';
  static const String appVersion = '1.0.0';

  // API Configuration
  static const String ftcApiBaseUrl = 'https://ftc-api.firstinspires.org/v2.0';
  static const String localApiBaseUrl = 'http://localhost:8000/api';

  // Environment variables - these should be loaded from environment
  static const String? ftcApiUsername =
      String.fromEnvironment('FTC_API_USERNAME');
  static const String? ftcApiKey = String.fromEnvironment('FTC_API_KEY');

  // Current season
  static const int currentSeason = 2024;

  // Pagination
  static const int defaultPageSize = 50;
  static const int maxPageSize = 100;

  // Cache settings
  static const Duration cacheExpiration = Duration(minutes: 15);
  static const Duration longCacheExpiration = Duration(hours: 24);

  // UI Constants
  static const double defaultPadding = 16.0;
  static const double smallPadding = 8.0;
  static const double largePadding = 24.0;

  // Animation durations
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 400);
  static const Duration longAnimation = Duration(milliseconds: 600);

  // Breakpoints for responsive design
  static const double mobileBreakpoint = 600;
  static const double tabletBreakpoint = 1024;
  static const double desktopBreakpoint = 1440;

  // Feature flags
  static const bool enablePushNotifications = true;
  static const bool enableOfflineMode = true;
  static const bool enableAnalytics = false;

  // Development settings
  static const bool isDebugMode =
      bool.fromEnvironment('dart.vm.product') == false;
  static const bool showDebugInfo = isDebugMode;

  // Validation methods
  static bool get hasValidFtcApiCredentials {
    return ftcApiUsername != null &&
        ftcApiKey != null &&
        ftcApiUsername!.isNotEmpty &&
        ftcApiKey!.isNotEmpty;
  }

  static void validateConfiguration() {
    if (!hasValidFtcApiCredentials) {
      throw Exception(
          'FTC API credentials are missing. Please set FTC_API_USERNAME and FTC_API_KEY environment variables.');
    }
  }
}
