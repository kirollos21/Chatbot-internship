/// App-wide state: chosen language and the resident's compound.
///
/// A `ValueNotifier` behind an `InheritedNotifier` is enough here — there are
/// two pieces of state and no cross-screen orchestration. Reaching for a state
/// management package would add ceremony without removing any.
library;

import 'package:flutter/widgets.dart';

import 'api_client.dart';
import 'strings.dart';

class AppState extends ChangeNotifier {
  AppState({ApiClient? api}) : api = api ?? ApiClient();

  final ApiClient api;

  AppLanguage _language = AppLanguage.en;
  String? _compound;
  String? _phase;

  AppLanguage get language => _language;
  String get languageCode => _language.code;
  S get strings => S(_language);
  TextDirection get textDirection => _language.textDirection;

  /// Used for directory/browse calls, which only distinguish Arabic from
  /// non-Arabic. Franco reads the English fields.
  String get contentLanguage => _language == AppLanguage.ar ? 'ar' : 'en';

  String? get compound => _compound;
  String? get phase => _phase;

  void setLanguage(AppLanguage value) {
    if (_language == value) return;
    _language = value;
    notifyListeners();
  }

  void setCompound(String? value) {
    final cleaned = (value ?? '').trim();
    _compound = cleaned.isEmpty ? null : cleaned;
    notifyListeners();
  }

  void setPhase(String? value) {
    final cleaned = (value ?? '').trim();
    _phase = cleaned.isEmpty ? null : cleaned;
    notifyListeners();
  }

  @override
  void dispose() {
    api.close();
    super.dispose();
  }
}

class AppScope extends InheritedNotifier<AppState> {
  const AppScope({super.key, required AppState state, required super.child})
      : super(notifier: state);

  static AppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope is missing from the widget tree');
    return scope!.notifier!;
  }
}
