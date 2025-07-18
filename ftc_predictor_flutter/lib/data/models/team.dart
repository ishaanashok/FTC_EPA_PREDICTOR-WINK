import 'package:json_annotation/json_annotation.dart';
import 'package:equatable/equatable.dart';

part 'team.g.dart';

@JsonSerializable()
class Team extends Equatable {
  final int teamNumber;
  final String nameShort;
  final String nameFull;
  final String city;
  final String stateProv;
  final String country;
  final String? website;
  final int? rookieYear;
  final int? season;
  final String? schoolName;
  final String? state;
  final DateTime? lastUpdated;

  const Team({
    required this.teamNumber,
    required this.nameShort,
    required this.nameFull,
    required this.city,
    required this.stateProv,
    required this.country,
    this.website,
    this.rookieYear,
    this.season,
    this.schoolName,
    this.state,
    this.lastUpdated,
  });

  factory Team.fromJson(Map<String, dynamic> json) => _$TeamFromJson(json);
  Map<String, dynamic> toJson() => _$TeamToJson(this);

  Team copyWith({
    int? teamNumber,
    String? nameShort,
    String? nameFull,
    String? city,
    String? stateProv,
    String? country,
    String? website,
    int? rookieYear,
    int? season,
    String? schoolName,
    String? state,
    DateTime? lastUpdated,
  }) {
    return Team(
      teamNumber: teamNumber ?? this.teamNumber,
      nameShort: nameShort ?? this.nameShort,
      nameFull: nameFull ?? this.nameFull,
      city: city ?? this.city,
      stateProv: stateProv ?? this.stateProv,
      country: country ?? this.country,
      website: website ?? this.website,
      rookieYear: rookieYear ?? this.rookieYear,
      season: season ?? this.season,
      schoolName: schoolName ?? this.schoolName,
      state: state ?? this.state,
      lastUpdated: lastUpdated ?? this.lastUpdated,
    );
  }

  @override
  List<Object?> get props => [
        teamNumber,
        nameShort,
        nameFull,
        city,
        stateProv,
        country,
        website,
        rookieYear,
        season,
        schoolName,
        state,
        lastUpdated,
      ];
}
