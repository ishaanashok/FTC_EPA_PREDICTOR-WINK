import 'package:json_annotation/json_annotation.dart';
import 'package:equatable/equatable.dart';

part 'event.g.dart';

@JsonSerializable()
class Event extends Equatable {
  final String code;
  final String name;
  final String type;
  final String city;
  final String stateProv;
  final String country;
  final String dateStart;
  final String dateEnd;
  final String? venue;
  final String? address;
  final String? timezone;
  final String? website;
  final String? liveStreamUrl;
  final int? teamCount;
  final int? matchCount;
  final int? season;
  final DateTime? lastUpdated;

  const Event({
    required this.code,
    required this.name,
    required this.type,
    required this.city,
    required this.stateProv,
    required this.country,
    required this.dateStart,
    required this.dateEnd,
    this.venue,
    this.address,
    this.timezone,
    this.website,
    this.liveStreamUrl,
    this.teamCount,
    this.matchCount,
    this.season,
    this.lastUpdated,
  });

  factory Event.fromJson(Map<String, dynamic> json) => _$EventFromJson(json);
  Map<String, dynamic> toJson() => _$EventToJson(this);

  Event copyWith({
    String? code,
    String? name,
    String? type,
    String? city,
    String? stateProv,
    String? country,
    String? dateStart,
    String? dateEnd,
    String? venue,
    String? address,
    String? timezone,
    String? website,
    String? liveStreamUrl,
    int? teamCount,
    int? matchCount,
    int? season,
    DateTime? lastUpdated,
  }) {
    return Event(
      code: code ?? this.code,
      name: name ?? this.name,
      type: type ?? this.type,
      city: city ?? this.city,
      stateProv: stateProv ?? this.stateProv,
      country: country ?? this.country,
      dateStart: dateStart ?? this.dateStart,
      dateEnd: dateEnd ?? this.dateEnd,
      venue: venue ?? this.venue,
      address: address ?? this.address,
      timezone: timezone ?? this.timezone,
      website: website ?? this.website,
      liveStreamUrl: liveStreamUrl ?? this.liveStreamUrl,
      teamCount: teamCount ?? this.teamCount,
      matchCount: matchCount ?? this.matchCount,
      season: season ?? this.season,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }

  @override
  List<Object?> get props => [
        code,
        name,
        type,
        city,
        stateProv,
        country,
        dateStart,
        dateEnd,
        venue,
        address,
        timezone,
        website,
        liveStreamUrl,
        teamCount,
        matchCount,
        season,
        lastUpdated,
      ];
}
