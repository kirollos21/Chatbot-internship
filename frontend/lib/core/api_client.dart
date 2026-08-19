/// Thin HTTP client for the Palm Hills backend.
///
/// The client stays deliberately dumb: no caching, no retries that could mask a
/// stale answer, no client-side interpretation of policy. Every field the UI
/// shows — the fine, the rule text, the "not configured" notice, the source IDs
/// — is decided by the backend, which is the only place the verified dataset
/// lives.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart' show MediaType;

import 'config.dart';
import 'models.dart';

class ApiException implements Exception {
  ApiException(this.message, {this.statusCode});

  final String message;
  final int? statusCode;

  bool get isOffline => statusCode == null;

  @override
  String toString() => 'ApiException($statusCode): $message';
}

class ApiClient {
  ApiClient({http.Client? client, AppConfig? config})
      : _client = client ?? http.Client(),
        _config = config ?? AppConfig.current;

  final http.Client _client;
  final AppConfig _config;

  Uri _uri(String path, [Map<String, String?> query = const {}]) {
    final cleaned = <String, String>{
      for (final entry in query.entries)
        if (entry.value != null && entry.value!.isNotEmpty)
          entry.key: entry.value!,
    };
    return Uri.parse('${_config.baseUrl}/api/v1$path')
        .replace(queryParameters: cleaned.isEmpty ? null : cleaned);
  }

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (_config.apiKey.isNotEmpty) 'X-API-Key': _config.apiKey,
      };

  Future<dynamic> _send(Future<http.Response> Function() call) async {
    late http.Response response;
    try {
      response = await call().timeout(_config.timeout);
    } on http.ClientException {
      // Raised on every platform, including web, where dart:io does not exist.
      throw ApiException('offline');
    } catch (_) {
      throw ApiException('offline');
    }

    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(utf8.decode(response.bodyBytes));
    }

    String detail = 'Request failed';
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      if (body is Map && body['detail'] != null) detail = '${body['detail']}';
    } catch (_) {
      // keep the generic message
    }
    throw ApiException(detail, statusCode: response.statusCode);
  }

  // --- assistant -------------------------------------------------------

  /// [language] forces the answer's language. Leave it null to let the backend
  /// answer in whatever language the resident wrote in — that is what lets a
  /// Franco question come back in Franco without Franco being a UI language.
  Future<ChatAnswer> ask({
    required String message,
    String? language,
    String? compound,
    String? phase,
    String? userId,
    String? sessionId,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/chat'),
          headers: _headers,
          body: jsonEncode({
            'message': message,
            if (language != null) 'language': language,
            if (compound != null && compound.isNotEmpty) 'compound': compound,
            if (phase != null && phase.isNotEmpty) 'phase': phase,
            if (userId != null) 'user_id': userId,
            if (sessionId != null) 'session_id': sessionId,
          }),
        ));
    return ChatAnswer.fromJson(body as Map<String, dynamic>);
  }

  // --- catalog ---------------------------------------------------------

  /// The Palm Hills projects offered in the location picker. Served by the
  /// backend so a corrected or new project does not need an app release.
  Future<List<Project>> projects() async {
    final body = await _send(() => _client.get(_uri('/projects'), headers: _headers));
    return (body as List).map((e) => Project.fromJson(e)).toList();
  }

  Future<List<Category>> categories() async {
    final body = await _send(() => _client.get(_uri('/categories'), headers: _headers));
    return (body as List).map((e) => Category.fromJson(e)).toList();
  }

  Future<List<Policy>> policies({String? categoryId, String? compound}) async {
    final body = await _send(() => _client.get(
        _uri('/policies', {'category_id': categoryId, 'compound': compound, 'limit': '500'}),
        headers: _headers));
    return (body as List).map((e) => Policy.fromJson(e)).toList();
  }

  Future<List<Violation>> violations({String? categoryId, String? compound}) async {
    final body = await _send(() => _client.get(
        _uri('/violations', {'category_id': categoryId, 'compound': compound, 'limit': '500'}),
        headers: _headers));
    return (body as List).map((e) => Violation.fromJson(e)).toList();
  }

  Future<List<Facility>> facilities({String? compound, String language = 'en'}) async {
    final body = await _send(() => _client.get(
        _uri('/facilities', {'compound': compound, 'language': language}),
        headers: _headers));
    return (body as List).map((e) => Facility.fromJson(e)).toList();
  }

  Future<List<Contact>> contacts({String? role, String language = 'en'}) async {
    final body = await _send(() => _client.get(
        _uri('/contacts', {'role': role, 'language': language}),
        headers: _headers));
    return (body as List).map((e) => Contact.fromJson(e)).toList();
  }

  // --- support ---------------------------------------------------------

  Future<List<Ticket>> tickets({String? userId}) async {
    final body = await _send(
        () => _client.get(_uri('/tickets', {'user_id': userId}), headers: _headers));
    return (body as List).map((e) => Ticket.fromJson(e)).toList();
  }

  Future<ViolationReport> createReport({
    required String description,
    String? categoryId,
    String? locationText,
    String? compound,
    String? phase,
    String? userId,
  }) async {
    final body = await _send(() => _client.post(
          _uri('/reports'),
          headers: _headers,
          body: jsonEncode({
            'description': description,
            if (categoryId != null) 'category_id': categoryId,
            if (locationText != null && locationText.isNotEmpty)
              'location_text': locationText,
            if (compound != null && compound.isNotEmpty) 'compound': compound,
            if (phase != null && phase.isNotEmpty) 'phase': phase,
            if (userId != null) 'user_id': userId,
          }),
        ));
    return ViolationReport.fromJson(body as Map<String, dynamic>);
  }

  Future<List<ViolationReport>> reports({String? userId}) async {
    final body = await _send(
        () => _client.get(_uri('/reports', {'user_id': userId}), headers: _headers));
    return (body as List).map((e) => ViolationReport.fromJson(e)).toList();
  }

  /// Uploads evidence for a report. The backend validates type, size and magic
  /// bytes and rejects anything that is not a real image.
  Future<ViolationReport> attachEvidence({
    required String reportId,
    required List<int> bytes,
    required String filename,
    required String contentType,
  }) async {
    final request = http.MultipartRequest(
      'POST',
      _uri('/reports/$reportId/attachments'),
    );
    if (_config.apiKey.isNotEmpty) {
      request.headers['X-API-Key'] = _config.apiKey;
    }
    final parts = contentType.split('/');
    request.files.add(http.MultipartFile.fromBytes(
      'file',
      bytes,
      filename: filename,
      contentType: parts.length == 2 ? MediaType(parts[0], parts[1]) : null,
    ));

    final streamed = await _client.send(request).timeout(_config.timeout);
    final response = await http.Response.fromStream(streamed);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return ViolationReport.fromJson(
          jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>);
    }
    String detail = 'Upload failed';
    try {
      final body = jsonDecode(utf8.decode(response.bodyBytes));
      if (body is Map && body['detail'] != null) detail = '${body['detail']}';
    } catch (_) {}
    throw ApiException(detail, statusCode: response.statusCode);
  }

  void close() => _client.close();
}
