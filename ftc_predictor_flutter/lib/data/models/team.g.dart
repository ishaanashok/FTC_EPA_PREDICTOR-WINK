// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'team.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

Team _$TeamFromJson(Map<String, dynamic> json) => Team(
      teamNumber: (json['teamNumber'] as num).toInt(),
      nameShort: json['nameShort'] as String,
      nameFull: json['nameFull'] as String,
      city: json['city'] as String,
      stateProv: json['stateProv'] as String,
      country: json['country'] as String,
      website: json['website'] as String?,
      rookieYear: (json['rookieYear'] as num?)?.toInt(),
      season: (json['season'] as num?)?.toInt(),
      schoolName: json['schoolName'] as String?,
      state: json['state'] as String?,
      lastUpdated: json['lastUpdated'] == null
          ? null
          : DateTime.parse(json['lastUpdated'] as String),
    );

Map<String, dynamic> _$TeamToJson(Team instance) => <String, dynamic>{
      'teamNumber': instance.teamNumber,
      'nameShort': instance.nameShort,
      'nameFull': instance.nameFull,
      'city': instance.city,
      'stateProv': instance.stateProv,
      'country': instance.country,
      'website': instance.website,
      'rookieYear': instance.rookieYear,
      'season': instance.season,
      'schoolName': instance.schoolName,
      'state': instance.state,
      'lastUpdated': instance.lastUpdated?.toIso8601String(),
    };
