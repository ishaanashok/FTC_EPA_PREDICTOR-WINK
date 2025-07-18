// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'event.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Event _$EventFromJson(Map<String, dynamic> json) => Event(
      code: json['code'] as String,
      name: json['name'] as String,
      type: json['type'] as String,
      city: json['city'] as String,
      stateProv: json['stateProv'] as String,
      country: json['country'] as String,
      dateStart: json['dateStart'] as String,
      dateEnd: json['dateEnd'] as String,
      venue: json['venue'] as String?,
      address: json['address'] as String?,
      timezone: json['timezone'] as String?,
      website: json['website'] as String?,
      liveStreamUrl: json['liveStreamUrl'] as String?,
      teamCount: (json['teamCount'] as num?)?.toInt(),
      matchCount: (json['matchCount'] as num?)?.toInt(),
      season: (json['season'] as num?)?.toInt(),
      lastUpdated: json['lastUpdated'] == null
          ? null
          : DateTime.parse(json['lastUpdated'] as String),
    );

Map<String, dynamic> _$EventToJson(Event instance) => <String, dynamic>{
      'code': instance.code,
      'name': instance.name,
      'type': instance.type,
      'city': instance.city,
      'stateProv': instance.stateProv,
      'country': instance.country,
      'dateStart': instance.dateStart,
      'dateEnd': instance.dateEnd,
      'venue': instance.venue,
      'address': instance.address,
      'timezone': instance.timezone,
      'website': instance.website,
      'liveStreamUrl': instance.liveStreamUrl,
      'teamCount': instance.teamCount,
      'matchCount': instance.matchCount,
      'season': instance.season,
      'lastUpdated': instance.lastUpdated?.toIso8601String(),
    };
