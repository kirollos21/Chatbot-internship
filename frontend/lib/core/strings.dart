/// UI strings.
///
/// The interface is offered in English and Arabic — see [AppLanguage.uiChoices].
/// Franco-Arabic is a *written* language here, not a chosen one: a resident who
/// types Franco in the chat is answered in Franco, but nobody picks Franco as an
/// interface. It has no BCP-47 code, no `intl` support and no standard
/// orthography, so treating it as a UI locale asks residents to read an
/// interface in a language that has no agreed spelling.
///
/// [AppLanguage.franco] therefore stays in the enum: the backend still reports
/// `language: "franco"` on an answer, and the app needs to be able to name that.
/// Its UI strings are kept so the type stays total, but no picker offers them.
///
/// This is a plain map rather than `flutter_localizations`/ARB because Franco
/// cannot be represented as a locale at all. Arabic still gets correct RTL via
/// [AppLanguage.textDirection].
library;

import 'package:flutter/widgets.dart';

enum AppLanguage {
  en('en', 'English', TextDirection.ltr),
  ar('ar', 'العربية', TextDirection.rtl),
  franco('franco', 'Franco', TextDirection.ltr);

  const AppLanguage(this.code, this.label, this.textDirection);

  final String code;
  final String label;
  final TextDirection textDirection;

  /// The languages the interface is offered in. Franco is excluded on purpose;
  /// it is a language the assistant *answers* in, never one you select.
  static const List<AppLanguage> uiChoices = [en, ar];

  /// The direction to lay an answer out in, given the language the backend says
  /// it wrote. Franco is Arabic in Latin script, so it reads left-to-right even
  /// when the surrounding interface is Arabic.
  static TextDirection directionFor(String languageCode) =>
      languageCode == 'ar' ? TextDirection.rtl : TextDirection.ltr;
}

class S {
  const S(this.language);

  final AppLanguage language;

  String _pick(String en, String ar, String franco) => switch (language) {
        AppLanguage.en => en,
        AppLanguage.ar => ar,
        AppLanguage.franco => franco,
      };

  // --- app shell -------------------------------------------------------
  String get appTitle => _pick(
        'Palm Hills Assistant',
        'مساعد بالم هيلز',
        'Palm Hills Assistant',
      );

  String get home => _pick('Home', 'الرئيسية', 'El Ra2iseya');
  String get assistant => _pick('Assistant', 'المساعد', 'El Mosa3ed');
  String get policies => _pick('Rules', 'اللوائح', 'El Lawa2e7');
  String get violations => _pick('Fines', 'الغرامات', 'El Gharamat');
  String get facilities => _pick('Facilities', 'المرافق', 'El Facilities');
  String get contacts => _pick('Contacts', 'أرقام التواصل', 'El Arkam');
  String get reportViolation =>
      _pick('Report', 'إبلاغ', 'Balagh');
  String get myRequests => _pick('My Requests', 'طلباتي', 'Talabaty');

  /// Named `languageLabel`, not `language`: the field `AppLanguage language`
  /// already occupies that name, and shadowing it made `_pick` switch on a
  /// String instead of the enum.
  String get languageLabel => _pick('Language', 'اللغة', 'El Logha');

  // --- home ------------------------------------------------------------
  /// Sits above the greeting in the hero. Names the community rather than the
  /// app, which is what makes the header feel like Palm Hills.
  String get communityName => _pick(
        'PALM HILLS COMMUNITIES',
        'مجتمعات بالم هيلز',
        'PALM HILLS COMMUNITIES',
      );
  String get askAssistant => _pick(
        'Ask the assistant',
        'اسأل المساعد',
        'Es2al el assistant',
      );
  String get browse => _pick('BROWSE', 'تصفح', 'BROWSE');
  String get chooseProject => _pick(
        'Choose your project',
        'اختر مشروعك',
        'Ekhtar el project bet3ak',
      );
  String get chooseProjectHint => _pick(
        'Answers are scoped to the project you select.',
        'الإجابات تتحدد حسب المشروع الذي تختاره.',
        'El egabat hatetkhaded 3ala hasab el project.',
      );
  String get noProjectHint => _pick(
        'Community-wide rules only',
        'اللوائح العامة للمجتمع فقط',
        'Lawa2e7 el mogtama3 el 3amma bas',
      );
  String get homeGreeting => _pick(
        'How can I help you today?',
        'كيف أقدر أساعدك النهاردة؟',
        'A2dar asa3dak ezay el naharda?',
      );
  String get homeSubtitle => _pick(
        'Ask about community rules, fines, facilities and contacts.',
        'اسأل عن لوائح المجتمع والغرامات والمرافق وأرقام التواصل.',
        'Es2al 3an lawa2e7 el mogtama3, el gharamat, el facilities wel arkam.',
      );

  // --- assistant -------------------------------------------------------
  /// Says out loud that Franco is accepted. Without this the only way a
  /// resident discovers it is by guessing, now that Franco is not in the
  /// language menu.
  String get writeAnyLanguage => _pick(
        'Write in English, Arabic or Franco — the answer comes back in the same language.',
        'اكتب بالعربية أو الإنجليزية أو الفرانكو — والرد يجيك بنفس اللغة.',
        'Ekteb bel 3arabi, English aw Franco — el radd hayeegy be nafs el logha.',
      );
  String get askPlaceholder => _pick(
        'Ask a question…',
        'اكتب سؤالك…',
        'Ektib so2alak…',
      );
  String get send => _pick('Send', 'إرسال', 'Eb3at');
  String get thinking => _pick('Checking the regulations…', 'بيراجع اللوائح…',
      'Bayraga3 el lawa2e7…');
  String get sources => _pick('Source', 'المصدر', 'Source');
  String get escalated => _pick(
        'Sent to Community Management',
        'تم التحويل إلى إدارة المجتمعات',
        'Etba3at le Community Management',
      );
  String get ticketRef => _pick('Ticket', 'رقم الطلب', 'Ticket');
  String get lowConfidence => _pick(
        'Not verified',
        'غير مؤكد',
        'Mesh mo2akkad',
      );
  String get needsCompound => _pick(
        'Depends on your compound',
        'يعتمد على الكمبوند',
        'Bey3temed 3ala el compound',
      );

  // --- shared ----------------------------------------------------------
  String get search => _pick('Search', 'بحث', 'Bahs');
  String get all => _pick('All', 'الكل', 'El Kol');
  String get retry => _pick('Retry', 'إعادة المحاولة', 'Hawel tany');
  String get loading => _pick('Loading…', 'جارٍ التحميل…', 'Bey7ammel…');
  String get nothingFound =>
      _pick('Nothing found.', 'لا توجد نتائج.', 'Mafeesh nataeg.');
  String get offline => _pick(
        'Cannot reach the service. Is the backend running?',
        'تعذر الوصول إلى الخدمة. هل الخادم يعمل؟',
        'Mesh 2ader awsal lel service. El backend shaghal?',
      );
  String get fine => _pick('Fine', 'الغرامة', 'El Ghrama');
  String get action => _pick('Action taken', 'الإجراء المتخذ', 'El Egraa2');
  String get egp => _pick('EGP', 'جنيه', 'EGP');

  // --- placeholder safety ----------------------------------------------
  /// Shown instead of a phone number that Palm Hills has not supplied yet.
  /// Never render a masked value such as XXXXXXXXXX to a resident.
  String get notConfigured => _pick(
        'Not available yet',
        'غير متاح حتى الآن',
        'Lessa mesh mawgood',
      );
  String get hoursNotConfigured => _pick(
        'Hours not published yet',
        'المواعيد غير معلنة حتى الآن',
        'El mawa3eed lessa mesh matnashara',
      );

  // --- report ----------------------------------------------------------
  String get reportTitle => _pick(
        'Report a violation',
        'الإبلاغ عن مخالفة',
        'Balagh 3an mokhalfa',
      );
  String get category => _pick('Category', 'الفئة', 'El Category');
  String get description => _pick('What happened?', 'ماذا حدث؟', 'Eh elli 7asal?');
  String get location => _pick('Location', 'المكان', 'El Makan');
  String get attachPhoto =>
      _pick('Attach a photo', 'إرفاق صورة', 'Erfa2 soura');
  String get submit => _pick('Submit', 'إرسال', 'Eb3at');
  String get cancel => _pick('Cancel', 'إلغاء', 'Elgha2');
  String get reportSubmitted => _pick(
        'Report submitted',
        'تم إرسال البلاغ',
        'El balagh etba3at',
      );
  String get reportDisclaimer => _pick(
        'Community Management reviews every report. A report is not a confirmed '
            'violation until staff verify it.',
        'تراجع إدارة المجتمعات كل بلاغ. البلاغ لا يُعد مخالفة مؤكدة إلا بعد '
            'التحقق منه.',
        'Community Management bteraga3 kol balagh. El balagh mesh mokhalfa '
            'mo2akkada gher lamma el staff yet2akkedo.',
      );
  String get descriptionRequired => _pick(
        'Please describe what happened.',
        'من فضلك اكتب ما حدث.',
        'Men fadlak ektib eh elli 7asal.',
      );

  // --- tickets ---------------------------------------------------------
  String get noTickets => _pick(
        'No requests yet.',
        'لا توجد طلبات.',
        'Mafeesh talabat lessa.',
      );
  String statusLabel(String status) => switch (status) {
        'open' => _pick('Open', 'مفتوح', 'Maftooh'),
        'in_review' => _pick('In review', 'قيد المراجعة', 'Taht el moraga3a'),
        'awaiting_user' =>
          _pick('Awaiting you', 'في انتظار ردك', 'Mestanni radak'),
        'resolved' => _pick('Resolved', 'تم الحل', 'Etthal'),
        'closed' => _pick('Closed', 'مغلق', 'Ma2fool'),
        _ => status,
      };

  // --- settings --------------------------------------------------------
  String get compound => _pick('Your project', 'مشروعك', 'El project bet3ak');
  String get compoundHint => _pick(
        'Tap to choose your Palm Hills project',
        'اضغط لاختيار مشروعك في بالم هيلز',
        'Eddos le tekhtar el project bet3ak fe Palm Hills',
      );
  String get notSet => _pick('Not set', 'غير محدد', 'Mesh mehaddad');
}
