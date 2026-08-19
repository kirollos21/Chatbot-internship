/// App-wide state: chosen language and the resident's compound.
///
/// A `ValueNotifier` behind an `InheritedNotifier` is enough here — there are
/// two pieces of state and no cross-screen orchestration. Reaching for a state
/// management package would add ceremony without removing any.
library;

import 'package:flutter/widgets.dart';

import 'api_client.dart';
import 'models.dart';
import 'strings.dart';

class AppState extends ChangeNotifier {
  AppState({ApiClient? api}) : api = api ?? ApiClient();

  final ApiClient api;

  AppLanguage _language = AppLanguage.en;
  Project? _project;
  String? _phase;

  AppLanguage get language => _language;
  String get languageCode => _language.code;
  S get strings => S(_language);
  TextDirection get textDirection => _language.textDirection;

  /// Used for directory/browse calls, which only distinguish Arabic from
  /// non-Arabic. Franco reads the English fields.
  String get contentLanguage => _language == AppLanguage.ar ? 'ar' : 'en';

  /// The resident's selected project, or null when they have not chosen one.
  Project? get project => _project;

  /// The scoping token sent to the API. Derived from the selected project rather
  /// than typed: a free-text compound could never match the backend's tokens, so
  /// it silently scoped every answer to community-wide rules.
  String? get compound => _project?.compound;

  String? get phase => _phase;

  void setLanguage(AppLanguage value) {
    if (_language == value) return;
    _language = value;
    notifyListeners();
  }

  void setProject(Project? value) {
    if (_project?.id == value?.id) return;
    _project = value;
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

  /// Registers the caller as a dependent, so it rebuilds when the language or
  /// the compound changes.
  ///
  /// Because this creates a dependency it must not be called from `initState`,
  /// where the element is not yet ready to take one. Screens that need state to
  /// build their request therefore start loading in `didChangeDependencies`,
  /// guarded so that only a change to the values the request actually uses
  /// triggers a refetch — that method also fires for unrelated dependencies
  /// such as `MediaQuery` when the keyboard opens.
  static AppState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope is missing from the widget tree');
    return scope!.notifier!;
  }
}
