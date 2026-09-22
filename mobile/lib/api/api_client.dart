import 'dart:convert';

import 'package:http/http.dart' as http;

import '../config.dart';

class ApiClient {
  ApiClient({http.Client? client, this.baseUrl = kApiBaseUrl})
      : _client = client ?? http.Client();

  final http.Client _client;
  final String baseUrl;

  Uri _uri(String path, [Map<String, String>? query]) {
    final normalized = path.startsWith('/') ? path : '/$path';
    final cleaned = query == null
        ? null
        : Map.fromEntries(
            query.entries.where((e) => e.value.isNotEmpty),
          );
    return Uri.parse('$baseUrl$normalized').replace(
      queryParameters: cleaned == null || cleaned.isEmpty ? null : cleaned,
    );
  }

  Map<String, String> _headers({bool jsonBody = false}) {
    return {
      'Accept': 'application/json',
      if (jsonBody) 'Content-Type': 'application/json',
    };
  }

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? query,
  }) async {
    final response = await _client.post(
      _uri(path, query),
      headers: _headers(jsonBody: true),
      body: jsonEncode(body),
    );
    return _decodeMap(response, 'POST', path);
  }

  Future<Map<String, dynamic>> getJson(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _client.get(
      _uri(path, query),
      headers: _headers(),
    );
    return _decodeMap(response, 'GET', path);
  }

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? query,
  }) async {
    final response = await _client.patch(
      _uri(path, query),
      headers: _headers(jsonBody: true),
      body: jsonEncode(body),
    );
    return _decodeMap(response, 'PATCH', path);
  }

  Future<Map<String, dynamic>> deleteJson(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _client.delete(
      _uri(path, query),
      headers: _headers(),
    );
    return _decodeMap(response, 'DELETE', path);
  }

  Future<dynamic> getJsonRaw(
    String path, {
    Map<String, String>? query,
  }) async {
    final response = await _client.get(
      _uri(path, query),
      headers: _headers(),
    );
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(
        'GET $path failed (${response.statusCode}): ${response.body}',
      );
    }
    if (response.body.isEmpty) return null;
    return jsonDecode(response.body);
  }

  Map<String, dynamic> _decodeMap(
    http.Response response,
    String method,
    String path,
  ) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception(
        '$method $path failed (${response.statusCode}): ${response.body}',
      );
    }
    if (response.body.isEmpty) return <String, dynamic>{};
    final decoded = jsonDecode(response.body);
    if (decoded is Map<String, dynamic>) return decoded;
    if (decoded is Map) return Map<String, dynamic>.from(decoded);
    throw Exception('$method $path: expected JSON object');
  }
}
