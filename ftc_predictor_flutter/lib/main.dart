import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/theme/app_theme.dart';
import 'core/config/app_config.dart';
import 'presentation/pages/home_page.dart';
import 'presentation/pages/teams_page.dart';
import 'presentation/pages/events_page.dart';
import 'package:go_router/go_router.dart';

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
    return MaterialApp.router(
      title: AppConfig.appName,
      theme: AppTheme.lightTheme,
      darkTheme: AppTheme.darkTheme,
      themeMode: ThemeMode.dark, // Default to dark theme
      routerConfig: _router,
      debugShowCheckedModeBanner: false,
    );
  }
}

final GoRouter _router = GoRouter(
  routes: [
    GoRoute(
      path: '/',
      builder: (context, state) => const HomePage(),
    ),
    GoRoute(
      path: '/teams',
      builder: (context, state) => const TeamsPage(),
    ),
    GoRoute(
      path: '/events',
      builder: (context, state) => const EventsPage(),
    ),
  ],
);
