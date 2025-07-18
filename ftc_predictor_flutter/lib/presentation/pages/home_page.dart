import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../core/config/app_config.dart';

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FTC Predictor'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppConfig.defaultPadding),
        child: Column(
          children: [
            // Hero section
            const SizedBox(height: 32),
            Text(
              'FTC Match Predictor',
              style: Theme.of(context).textTheme.displayMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 16),
            Text(
              'Advanced Match Prediction and Team Analysis',
              style: Theme.of(context).textTheme.headlineSmall,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 24),
            Container(
              constraints: const BoxConstraints(maxWidth: 800),
              child: Text(
                'WinSim uses advanced machine learning algorithms to analyze FTC team performance data, '
                'match histories, and competition statistics. Our predictive models help teams and '
                'event organizers make data-driven decisions by providing accurate match outcome '
                'predictions and detailed performance analytics.',
                style: Theme.of(context).textTheme.bodyLarge,
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 48),

            // Feature cards
            LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth > AppConfig.tabletBreakpoint) {
                  return Row(
                    children: [
                      Expanded(
                        child: _buildFeatureCard(
                          context,
                          'Team Analysis',
                          'View detailed team statistics, performance metrics, and historical data',
                          Icons.group,
                          () => context.go('/teams'),
                        ),
                      ),
                      const SizedBox(width: 16),
                      Expanded(
                        child: _buildFeatureCard(
                          context,
                          'Event Predictions',
                          'Get match predictions, event statistics, and tournament analysis',
                          Icons.emoji_events,
                          () => context.go('/events'),
                        ),
                      ),
                    ],
                  );
                } else {
                  return Column(
                    children: [
                      _buildFeatureCard(
                        context,
                        'Team Analysis',
                        'View detailed team statistics, performance metrics, and historical data',
                        Icons.group,
                        () => context.go('/teams'),
                      ),
                      const SizedBox(height: 16),
                      _buildFeatureCard(
                        context,
                        'Event Predictions',
                        'Get match predictions, event statistics, and tournament analysis',
                        Icons.emoji_events,
                        () => context.go('/events'),
                      ),
                    ],
                  );
                }
              },
            ),

            const SizedBox(height: 64),

            // Statistics section
            Text(
              'FTC Predictor by the Numbers',
              style: Theme.of(context).textTheme.headlineMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 32),

            LayoutBuilder(
              builder: (context, constraints) {
                if (constraints.maxWidth > AppConfig.tabletBreakpoint) {
                  return Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _buildStatCard(
                          context, '7,000+', 'Active Teams', Icons.people),
                      _buildStatCard(
                          context, '150+', 'Events Analyzed', Icons.event),
                      _buildStatCard(context, '90%', 'Prediction Accuracy',
                          Icons.bar_chart),
                    ],
                  );
                } else {
                  return Column(
                    children: [
                      _buildStatCard(
                          context, '7,000+', 'Active Teams', Icons.people),
                      const SizedBox(height: 16),
                      _buildStatCard(
                          context, '150+', 'Events Analyzed', Icons.event),
                      const SizedBox(height: 16),
                      _buildStatCard(context, '90%', 'Prediction Accuracy',
                          Icons.bar_chart),
                    ],
                  );
                }
              },
            ),

            const SizedBox(height: 64),
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureCard(
    BuildContext context,
    String title,
    String description,
    IconData icon,
    VoidCallback onTap,
  ) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(16),
        child: Container(
          padding: const EdgeInsets.all(AppConfig.largePadding),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 60,
                color: Theme.of(context).colorScheme.primary,
              ),
              const SizedBox(height: 16),
              Text(
                title,
                style: Theme.of(context).textTheme.headlineSmall,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 12),
              Text(
                description,
                style: Theme.of(context).textTheme.bodyMedium,
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 24),
              ElevatedButton(
                onPressed: onTap,
                child: Text(
                    title == 'Team Analysis' ? 'View Teams' : 'View Events'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildStatCard(
      BuildContext context, String value, String label, IconData icon) {
    return Card(
      child: Container(
        padding: const EdgeInsets.all(AppConfig.largePadding),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 48,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Text(
              value,
              style: Theme.of(context).textTheme.headlineMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              label,
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }
}
