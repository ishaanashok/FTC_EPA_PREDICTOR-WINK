import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class EventsPage extends StatefulWidget {
  const EventsPage({super.key});

  @override
  State<EventsPage> createState() => _EventsPageState();
}

class _EventsPageState extends State<EventsPage> {
  final TextEditingController _searchController = TextEditingController();
  List<Map<String, dynamic>> events = [];
  List<Map<String, dynamic>> filteredEvents = [];
  bool isLoading = false;
  String? error;
  String filter = 'all';

  @override
  void initState() {
    super.initState();
    _loadEvents(); // Load real events data automatically
  }

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
              'Inkistics - Events',
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
              'FTC Events',
              style: Theme.of(context).textTheme.displaySmall?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Discover and track FTC competitions and tournaments',
              style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                color: Colors.grey[600],
              ),
            ),
            const SizedBox(height: 24),

            // Search and Filter Section
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Search Events',
                      style: Theme.of(context).textTheme.titleLarge?.copyWith(
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(height: 16),
                    Row(
                      children: [
                        Expanded(
                          flex: 2,
                          child: TextField(
                            controller: _searchController,
                            decoration: const InputDecoration(
                              labelText: 'Search Events',
                              hintText: 'Enter event name or location',
                              border: OutlineInputBorder(),
                              prefixIcon: Icon(Icons.search),
                            ),
                            onChanged: _filterEvents,
                          ),
                        ),
                        const SizedBox(width: 16),
                        Expanded(
                          child: DropdownButtonFormField<String>(
                            value: filter,
                            decoration: const InputDecoration(
                              labelText: 'Filter',
                              border: OutlineInputBorder(),
                            ),
                            items: const [
                              DropdownMenuItem(value: 'upcoming', child: Text('Upcoming')),
                              DropdownMenuItem(value: 'ongoing', child: Text('Ongoing')),
                              DropdownMenuItem(value: 'past', child: Text('Past')),
                              DropdownMenuItem(value: 'all', child: Text('All Events')),
                            ],
                            onChanged: (value) {
                              setState(() {
                                filter = value!;
                              });
                              _filterEvents(_searchController.text);
                            },
                          ),
                        ),
                        const SizedBox(width: 16),
                        ElevatedButton.icon(
                          onPressed: _loadSampleEvents,
                          icon: const Icon(Icons.refresh),
                          label: const Text('Load Events'),
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
            Text('Loading events...'),
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

    if (filteredEvents.isEmpty) {
      return Center(
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.event, size: 64, color: Colors.grey),
                const SizedBox(height: 16),
                Text(
                  'No events found',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Try loading sample events or adjusting your search',
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                ElevatedButton.icon(
                  onPressed: _loadSampleEvents,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Load Sample Events'),
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
              'Events (${filteredEvents.length} found)',
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const Spacer(),
            Chip(
              label: Text(filter.toUpperCase()),
              backgroundColor: Theme.of(context).primaryColor.withOpacity(0.1),
            ),
          ],
        ),
        const SizedBox(height: 16),
        Expanded(
          child: GridView.builder(
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: MediaQuery.of(context).size.width > 800 ? 3 : 
                             MediaQuery.of(context).size.width > 600 ? 2 : 1,
              childAspectRatio: 1.2,
              crossAxisSpacing: 16,
              mainAxisSpacing: 16,
            ),
            itemCount: filteredEvents.length,
            itemBuilder: (context, index) {
              final event = filteredEvents[index];
              return _buildEventCard(event);
            },
          ),
        ),
      ],
    );
  }

  Widget _buildEventCard(Map<String, dynamic> event) {
    return Card(
      elevation: 3,
      child: InkWell(
        onTap: () {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text('Event details for ${event['name']} not yet implemented'),
            ),
          );
        },
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Event Status Chip
              Row(
                children: [
                  Chip(
                    label: Text(
                      event['status'] ?? 'Unknown',
                      style: const TextStyle(fontSize: 12),
                    ),
                    backgroundColor: _getStatusColor(event['status']),
                  ),
                  const Spacer(),
                  Icon(
                    Icons.event,
                    color: Colors.grey[600],
                    size: 20,
                  ),
                ],
              ),
              const SizedBox(height: 12),
              
              // Event Name
              Text(
                event['name'] ?? 'Unknown Event',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
              const SizedBox(height: 8),
              
              // Location
              Row(
                children: [
                  Icon(Icons.location_on, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      '${event['venue'] ?? 'Unknown Venue'}\n${event['city'] ?? 'Unknown'}, ${event['stateProv'] ?? 'Unknown'}',
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        color: Colors.grey[600],
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              
              // Date
              Row(
                children: [
                  Icon(Icons.calendar_today, size: 16, color: Colors.grey[600]),
                  const SizedBox(width: 4),
                  Text(
                    event['dateStart'] ?? 'Date TBD',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
              
              const Spacer(),
              
              // Teams Count
              if (event['teamsCount'] != null)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Theme.of(context).primaryColor.withOpacity(0.1),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    '${event['teamsCount']} teams',
                    style: TextStyle(
                      color: Theme.of(context).primaryColor,
                      fontWeight: FontWeight.bold,
                      fontSize: 12,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Color _getStatusColor(String? status) {
    switch (status?.toLowerCase()) {
      case 'upcoming':
        return Colors.blue.withOpacity(0.2);
      case 'ongoing':
        return Colors.green.withOpacity(0.2);
      case 'past':
        return Colors.grey.withOpacity(0.2);
      default:
        return Colors.orange.withOpacity(0.2);
    }
  }

  void _filterEvents(String searchText) {
    setState(() {
      filteredEvents = events.where((event) {
        final matchesSearch = searchText.isEmpty ||
            (event['name'] ?? '').toLowerCase().contains(searchText.toLowerCase()) ||
            (event['city'] ?? '').toLowerCase().contains(searchText.toLowerCase()) ||
            (event['venue'] ?? '').toLowerCase().contains(searchText.toLowerCase());
        
        if (filter == 'all') {
          return matchesSearch;
        }
        
        // Calculate the event status dynamically based on dates
        final eventStatus = _getEventStatus(event);
        final matchesFilter = eventStatus == filter;
        
        return matchesSearch && matchesFilter;
      }).toList();
    });
  }

  void _loadSampleEvents() {
    _loadEvents();
  }

  Future<void> _loadEvents() async {
    setState(() {
      isLoading = true;
      error = null;
    });

    try {
      // Use season 2024 to match the data in DynamoDB
      const season = 2024;
      const apiUrl = 'https://emgquhzu1f.execute-api.us-east-1.amazonaws.com/stage';
      
      final uri = Uri.parse('$apiUrl/api/events?season=$season');
      
      print('EventsPage: Making request to $uri');
      
      final response = await http.get(
        uri,
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json',
        },
      ).timeout(const Duration(seconds: 30));

      print('EventsPage: Response status: ${response.statusCode}');
      print('EventsPage: Response body: ${response.body}');

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          final eventsData = data['events'] as List? ?? [];
          
          // Debug: Print first event to understand field names
          if (eventsData.isNotEmpty) {
            print('Sample event keys: ${eventsData.first.keys.toList()}');
            print('Sample event data: ${eventsData.first}');
          }
          
          setState(() {
            events = eventsData.map((event) {
              final eventObj = {
                'name': event['eventName'] ?? event['name'] ?? event['fullName'] ?? event['displayName'] ?? 'Unknown Event',
                'venue': event['venue'] ?? event['venueName'] ?? 'Unknown Venue',
                'city': event['city'] ?? event['cityName'] ?? 'Unknown City',
                'stateProv': event['state'] ?? event['stateProv'] ?? event['stateProvince'] ?? '',
                'country': event['country'] ?? event['countryCode'] ?? 'USA',
                'dateStart': event['dateStart'] ?? event['startDate'] ?? '',
                'dateEnd': event['dateEnd'] ?? event['endDate'] ?? '',
                'teamsCount': event['teamCount'] ?? event['teamsCount'] ?? event['numberOfTeams'] ?? 0,
                'eventCode': event['eventCode'] ?? event['code'] ?? '',
              };
              eventObj['status'] = _getEventStatus(eventObj);
              return eventObj;
            }).toList();
            filteredEvents = events;
            isLoading = false;
          });
          
          _filterEvents(_searchController.text);
          print('EventsPage: Loaded ${events.length} events successfully');
        } else {
          throw Exception('API returned success: false');
        }
      } else {
        throw Exception('HTTP ${response.statusCode}: ${response.body}');
      }
    } catch (e) {
      print('EventsPage: Error loading events: $e');
      setState(() {
        isLoading = false;
        error = 'Failed to load events: $e';
        // Fall back to sample data
        events = _getSampleEvents();
        filteredEvents = events;
      });
    }
  }

  String _getEventStatus(Map<String, dynamic> event) {
    // Get both start and end dates if available
    final dateStart = event['dateStart'] as String?;
    final dateEnd = event['dateEnd'] as String?;
    
    if (dateStart == null || dateStart.isEmpty) {
      return 'unknown';
    }
    
    try {
      DateTime startDate;
      DateTime? endDate;
      
      // Handle multiple date formats common in FTC API
      startDate = _parseEventDate(dateStart);
      
      // Parse end date if available
      if (dateEnd != null && dateEnd.isNotEmpty) {
        try {
          endDate = _parseEventDate(dateEnd);
        } catch (e) {
          // If end date parsing fails, ignore it
          endDate = null;
        }
      }
      
      final now = DateTime.now();
      // Get today's date at midnight for proper date-only comparison
      final today = DateTime(now.year, now.month, now.day);
      
      // Determine status based on dates
      String status;
      if (endDate != null) {
        // If we have an end date, use it for better accuracy
        if (startDate.isAfter(today)) {
          status = 'upcoming';
        } else if (endDate.isBefore(today)) {
          status = 'past';
        } else {
          // Start date has passed but end date hasn't
          status = 'ongoing';
        }
      } else {
        // Only start date available, use simpler logic
        if (startDate.isAfter(today)) {
          status = 'upcoming';
        } else if (startDate.isBefore(today.subtract(const Duration(days: 2)))) {
          // Consider events older than 2 days as past
          status = 'past';
        } else {
          // Events within the last 2 days are considered ongoing
          status = 'ongoing';
        }
      }
      
      return status;
    } catch (e) {
      print('Error parsing date for event ${event['name']}: $e');
      return 'unknown';
    }
  }

  DateTime _parseEventDate(String dateString) {
    // Clean up the date string
    String cleanDate = dateString.trim();
    
    // Strip everything after 'T' to get just the date part
    if (cleanDate.contains('T')) {
      cleanDate = cleanDate.split('T')[0];
    }
    
    // Now we should have just "2024-01-15" format
    if (cleanDate.contains('-') && cleanDate.length >= 10) {
      // Parse as date only at midnight UTC for consistent comparison
      return DateTime.parse('${cleanDate}T00:00:00Z');
    } else {
      // Fallback - try to parse as-is
      return DateTime.parse(cleanDate);
    }
  }

  void _loadSampleEventsOld() {
    setState(() {
      isLoading = true;
      error = null;
    });

    Future.delayed(const Duration(milliseconds: 500), () {
      if (mounted) {
        setState(() {
          isLoading = false;
          events = _getSampleEvents();
          filteredEvents = events;
        });
        _filterEvents(_searchController.text);
      }
    });
  }

  List<Map<String, dynamic>> _getSampleEvents() {
    return [
      {
        'name': 'California State Championship',
        'venue': 'Sacramento Convention Center',
        'city': 'Sacramento',
        'stateProv': 'CA',
        'country': 'USA',
        'dateStart': '2024-03-15',
        'status': 'upcoming',
        'teamsCount': 64,
      },
      {
        'name': 'Texas Regional Qualifier',
        'venue': 'Houston Exhibition Hall',
        'city': 'Houston',
        'stateProv': 'TX',
        'country': 'USA',
        'dateStart': '2024-02-20',
        'status': 'ongoing',
        'teamsCount': 32,
      },
      {
        'name': 'New York Metro Championship',
        'venue': 'Brooklyn Sports Complex',
        'city': 'Brooklyn',
        'stateProv': 'NY',
        'country': 'USA',
        'dateStart': '2024-01-15',
        'status': 'past',
        'teamsCount': 48,
      },
      {
        'name': 'Florida State Qualifier',
        'venue': 'Orlando Convention Center',
        'city': 'Orlando',
        'stateProv': 'FL',
        'country': 'USA',
        'dateStart': '2024-04-10',
        'status': 'upcoming',
        'teamsCount': 56,
      },
      {
        'name': 'Midwest Regional',
        'venue': 'Chicago Exhibition Center',
        'city': 'Chicago',
        'stateProv': 'IL',
        'country': 'USA',
        'dateStart': '2024-03-25',
        'status': 'upcoming',
        'teamsCount': 40,
      },
    ];
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }
}
