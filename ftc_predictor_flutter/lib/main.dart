import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'core/config/app_config.dart';
import 'presentation/pages/home_page.dart';
import 'presentation/pages/teams_page.dart';
import 'presentation/pages/events_page.dart';

void main() {
  // Validate configuration
  try {
    AppConfig.validateConfiguration();
  } catch (e) {
    print('Configuration error: $e');
    // Continue with app but show error in UI
  }

  runApp(
    const ProviderScope(
      child: MyApp(),
    ),
  );
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'FTC Predictor',
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark,
      home: const HomePage(),
      routes: {
        '/teams': (context) => const TeamsPage(),
        '/events': (context) => const EventsPage(),
      },
      debugShowCheckedModeBanner: false,
    );
  }
}
