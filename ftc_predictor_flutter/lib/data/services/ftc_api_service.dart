import 'package:dio/dio.dart';
import 'package:retrofit/retrofit.dart';
import '../../core/config/app_config.dart';
import '../models/team.dart';
import '../models/event.dart';

part 'ftc_api_service.g.dart';

@RestApi(baseUrl: AppConfig.localApiBaseUrl)
abstract class FTCApiService {
  factory FTCApiService(Dio dio, {String baseUrl}) = _FTCApiService;

  // Team methods
  @GET('/teams/{season}')
  Future<Map<String, dynamic>> getTeams(
    @Path('season') int season, {
    @Query('teamNumber') int? teamNumber,
    @Query('eventCode') String? eventCode,
    @Query('page') int? page,
  });

  @GET('/teams/{teamNumber}/matches/{season}')
  Future<Map<String, dynamic>> getTeamSeasonMatches(
    @Path('teamNumber') int teamNumber,
    @Path('season') int season,
  );

  @GET('/teams/{teamNumber}/historical-matches')
  Future<Map<String, dynamic>> getHistoricalMatches(
    @Path('teamNumber') int teamNumber,
  );

  @GET('/teams/{teamNumber}/historical-epa')
  Future<Map<String, dynamic>> getHistoricalEPA(
    @Path('teamNumber') int teamNumber,
  );

  // Event methods
  @GET('/events/{season}')
  Future<Map<String, dynamic>> getEvents(
    @Path('season') int season, {
    @Query('eventCode') String? eventCode,
    @Query('teamNumber') int? teamNumber,
  });

  @GET('/events/{season}/{eventCode}/rankings')
  Future<Map<String, dynamic>> getEventRankings(
    @Path('season') int season,
    @Path('eventCode') String eventCode,
  );

  // Match methods
  @GET('/matches/{season}/{eventCode}')
  Future<Map<String, dynamic>> getEventMatches(
    @Path('season') int season,
    @Path('eventCode') String eventCode, {
    @Query('tournamentLevel') String? tournamentLevel,
    @Query('teamNumber') int? teamNumber,
  });

  @GET('/schedule/{season}/{eventCode}')
  Future<Map<String, dynamic>> getEventSchedule(
    @Path('season') int season,
    @Path('eventCode') String eventCode, {
    @Query('tournamentLevel') String? tournamentLevel,
    @Query('teamNumber') int? teamNumber,
    @Query('start') int? start,
    @Query('end') int? end,
  });

  // League methods
  @GET('/leagues/{season}')
  Future<Map<String, dynamic>> getLeagues(
    @Path('season') int season, {
    @Query('regionCode') String? regionCode,
    @Query('leagueCode') String? leagueCode,
  });

  @GET('/leagues/{season}/members/{regionCode}/{leagueCode}')
  Future<Map<String, dynamic>> getLeagueMembers(
    @Path('season') int season,
    @Path('regionCode') String regionCode,
    @Path('leagueCode') String leagueCode,
  );

  @GET('/leagues/{season}/rankings/{regionCode}/{leagueCode}')
  Future<Map<String, dynamic>> getLeagueRankings(
    @Path('season') int season,
    @Path('regionCode') String regionCode,
    @Path('leagueCode') String leagueCode,
  );

  // Advancement methods
  @GET('/advancement/{season}/{eventCode}')
  Future<Map<String, dynamic>> getEventAdvancement(
    @Path('season') int season,
    @Path('eventCode') String eventCode, {
    @Query('excludeSkipped') bool? excludeSkipped,
  });

  @GET('/advancement/{season}/{eventCode}/source')
  Future<Map<String, dynamic>> getAdvancementSource(
    @Path('season') int season,
    @Path('eventCode') String eventCode, {
    @Query('includeDeclines') bool? includeDeclines,
  });

  // Season data methods
  @GET('/season/{season}')
  Future<Map<String, dynamic>> getSeasonSummary(
    @Path('season') int season,
  );

  // Prediction methods
  @POST('/match-prediction')
  Future<Map<String, dynamic>> getMatchPrediction(
    @Body() Map<String, dynamic> predictionRequest,
  );

  @POST('/event-predictions-epa')
  Future<Map<String, dynamic>> getEventPredictionsAndEPA(
    @Body() Map<String, dynamic> request,
  );

  @POST('/alliance-matchmaker')
  Future<Map<String, dynamic>> getBestAlliancePartner(
    @Body() Map<String, dynamic> request,
  );

  @POST('/alliance-matchmaker/batch')
  Future<Map<String, dynamic>> getBestAlliancePartnersBatch(
    @Body() Map<String, dynamic> request,
  );
}

// Helper class to create configured Dio instance
class FTCApiClient {
  static Dio createDio() {
    final dio = Dio();

    // Add interceptors
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          // Add authentication headers if needed
          if (AppConfig.hasValidFtcApiCredentials) {
            options.headers['Authorization'] =
                'Basic ${AppConfig.ftcApiUsername}:${AppConfig.ftcApiKey}';
          }
          handler.next(options);
        },
        onError: (error, handler) {
          // Handle API errors
          print('API Error: ${error.message}');
          handler.next(error);
        },
      ),
    );

    // Add logging in debug mode
    if (AppConfig.isDebugMode) {
      dio.interceptors.add(LogInterceptor(
        requestBody: true,
        responseBody: true,
        requestHeader: true,
        responseHeader: true,
      ));
    }

    return dio;
  }

  static FTCApiService createService() {
    return FTCApiService(createDio());
  }
}
