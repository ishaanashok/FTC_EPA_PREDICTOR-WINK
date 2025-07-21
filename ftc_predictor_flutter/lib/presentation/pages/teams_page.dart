import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

class TeamsPage extends StatefulWidget {
  const TeamsPage({super.key});

  @override
  State<TeamsPage> createState() => _TeamsPageState();
}

class _TeamsPageState extends State<TeamsPage> {
  final TextEditingController _teamNumberController = TextEditingController();
  final TextEditingController _teamNameController = TextEditingController();
  List<Map<String, dynamic>> teams = [];
  List<Map<String, dynamic>> filteredTeams = [];
  bool isLoading = false;
  String? error;
  int currentPage = 1;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            CircleAvatar(
              radius: 20,
              backgroundImage: NetworkImage(
                'https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcT0Tvvq76mlrXBo5WZSHZe3JUqS9c6U0UKd6A&s',
              ),
            ),
            const SizedBox(width: 10),
            const Text(
              'Inkistics - Teams',
              style: TextStyle(fontWeight: FontWeight.bold),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => context.go('/'),
            child: const Text('Home', style: TextStyle(color: Colors.white)),
          ),
          TextButton(
            onPressed: () => context.go('/teams'),
            child: const Text('Teams', style: TextStyle(color: Colors.white)),
          ),
          TextButton(
            onPressed: () => context.go('/events'),
            child: const Text('Events', style: TextStyle(color: Colors.white)),
          ),
          const SizedBox(width: 16),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Title and Description
            Text(
              'FTC Teams',
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Search and explore FTC teams from around the world',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 24),

            // Search Section
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Search Teams',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _teamNumberController,
                            decoration: const InputDecoration(
                              labelText: 'Team Number',
                              hintText: 'Enter team number (e.g., 12345)',
                              border: OutlineInputBorder(),
                              prefixIcon: Icon(Icons.numbers),
                            ),
                            keyboardType: TextInputType.number,
                            onSubmitted: (_) => _handleSearch(),
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: TextField(
                            controller: _teamNameController,
                            decoration: const InputDecoration(
                              labelText: 'Team Name',
                              hintText: 'Enter team name',
                              border: OutlineInputBorder(),
                              prefixIcon: Icon(Icons.search),
                            ),
                            onSubmitted: (_) => _handleSearch(),
                          ),
                        ),
                        const SizedBox(width: 16),
                        ElevatedButton.icon(
                          onPressed: _handleSearch,
                          icon: const Icon(Icons.search),
                          label: const Text('Search'),
                          style: ElevatedButton.styleFrom(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 24,
                              vertical: 16,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),

            const SizedBox(height: 24),

            // Results Section
            Expanded(
              child: _buildResultsSection(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildResultsSection() {
    if (isLoading) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            CircularProgressIndicator(),
            SizedBox(height: 16),
            Text('Searching for teams...'),
          ],
        ),
      );
    }

    if (error != null) {
      return Center(
        child: Card(
          color: Colors.red[50],
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.error, color: Colors.red, size: 48),
                const SizedBox(height: 16),
                Text(
                  'Error: $error',
                  style: const TextStyle(color: Colors.red),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                ElevatedButton(
                  onPressed: () {
                    setState(() {
                      error = null;
                    });
                  },
                  child: const Text('Dismiss'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    if (filteredTeams.isEmpty && (teams.isEmpty)) {
      return Center(
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.search, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                Text(
                  'No teams found',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Try searching by team number or team name',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: _loadSampleTeams,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Load Sample Teams'),
                ),
              ],
            ),
          ),
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Teams (${filteredTeams.length} found)',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const Spacer(),
            IconButton(
              onPressed: _loadSampleTeams,
              icon: const Icon(Icons.refresh),
              tooltip: 'Refresh',
            ),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: ListView.builder(
            itemCount: filteredTeams.length,
            itemBuilder: (context, index) {
              final team = filteredTeams[index];
              return _buildTeamCard(team);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildTeamCard(Map<String, dynamic> team) {
    return Card(
      elevation: 2,
      margin: const EdgeInsets.only(bottom: 12),
      child: InkWell(
        onTap: () {
          // Navigate to team details (placeholder)
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Team ${team['teamNumber']} details not yet implemented'),
            ),
          );
        },
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Row(
            children: [
              // Team Number Circle
              Container(
                width: 60,
                height: 60,
                decoration: BoxDecoration(
                  color: Theme.of(context).primaryColor,
                  shape: BoxShape.circle,
                ),
                child: Center(
                  child: Text(
                    team['teamNumber'].toString(),
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              
              // Team Info
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      team['nameShort'] ?? 'Unknown Team',
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (team['nameFull'] != null)
                      Text(
                        team['nameFull'],
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: Colors.grey[600],
                        ),
                      ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Icon(Icons.location_on, size: 16, color: Colors.grey[600]),
                        const SizedBox(width: 4),
                        Text(
                          '${team['city'] ?? 'Unknown'}, ${team['stateProv'] ?? 'Unknown'}',
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              
              const Icon(Icons.arrow_forward_ios, size: 16),
            ],
          ),
        ),
      ),
    );
  }

  void _handleSearch() {
    final teamNumber = _teamNumberController.text.trim();
    final teamName = _teamNameController.text.trim();

    if (teamNumber.isEmpty && teamName.isEmpty) {
      setState(() {
        error = 'Please enter a team number or team name to search';
      });
      return;
    }

    setState(() {
      isLoading = true;
      error = null;
    });

    // Simulate API call
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        setState(() {
          isLoading = false;
          error = 'FTC API not configured. Please set up API credentials to search teams.';
        });
      }
    });
  }

  void _loadSampleTeams() {
    setState(() {
      isLoading = true;
      error = null;
    });

    // Load sample teams data
    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted) {
        setState(() {
          isLoading = false;
          teams = _getSampleTeams();
          filteredTeams = teams;
        });
      }
    });
  }

  List<Map<String, dynamic>> _getSampleTeams() {
    return [
      {
        'teamNumber': 12345,
        'nameShort': 'Sample Robotics',
        'nameFull': 'Sample High School Robotics Team',
        'city': 'Sample City',
        'stateProv': 'CA',
        'country': 'USA',
      },
      {
        'teamNumber': 54321,
        'nameShort': 'Test Squad',
        'nameFull': 'Test Middle School Squad',
        'city': 'Test Town',
        'stateProv': 'TX',
        'country': 'USA',
      },
      {
        'teamNumber': 11111,
        'nameShort': 'Demo Team',
        'nameFull': 'Demonstration Robotics Club',
        'city': 'Demo City',
        'stateProv': 'NY',
        'country': 'USA',
      },
      {
        'teamNumber': 99999,
        'nameShort': 'Example Bots',
        'nameFull': 'Example Academy Robot Team',
        'city': 'Example Springs',
        'stateProv': 'FL',
        'country': 'USA',
      },
    ];
  }

  @override
  void dispose() {
    _teamNumberController.dispose();
    _teamNameController.dispose();
    super.dispose();
  }
}
