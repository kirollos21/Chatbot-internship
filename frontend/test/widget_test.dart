import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:palm_hills_assistant/core/models.dart';
import 'package:palm_hills_assistant/core/strings.dart';
import 'package:palm_hills_assistant/widgets/common.dart';

void main() {
  group('penalty formatting', () {
    test('preserves the exact amount, adding separators only', () {
      Violation build(int penalty) => Violation.fromJson({
            'id': 'V034',
            'category_id': 'vehicle_regulations',
            'violation_en': 'Parking in a non-designated area',
            'violation_ar': 'ركن في مكان غير مخصص',
            'penalty_egp': penalty,
            'action_en': 'Placement of a violation sticker',
            'action_ar': 'وضع ملصق',
            'related_policy_ids': ['P040'],
          });

      expect(build(500).penaltyFormatted, '500');
      expect(build(5000).penaltyFormatted, '5,000');
      expect(build(10000).penaltyFormatted, '10,000');
      // The value itself must survive untouched.
      expect(build(500).penaltyEgp, 500);
      expect(build(5000).penaltyEgp, 5000);
    });
  });

  group('placeholder safety', () {
    test('a contact with no configured number exposes no phone', () {
      final contact = Contact.fromJson({
        'id': 'C001',
        'name_en': 'Security / Gate Control',
        'name_ar': 'الأمن',
        'role': 'security',
        'phone': null,
        'availability': 'not_configured',
        'message': 'This number has not been configured in the system yet.',
      });

      expect(contact.hasPhone, isFalse);
      expect(contact.phone, isNull);
      expect(contact.message, contains('not been configured'));
    });

    testWidgets('UnavailableNotice shows the message, never a masked value',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: Scaffold(
          body: UnavailableNotice(message: 'Not available yet'),
        ),
      ));

      expect(find.text('Not available yet'), findsOneWidget);
      expect(find.textContaining('XXXX'), findsNothing);
    });
  });

  group('languages', () {
    test('Arabic is right-to-left, English and Franco are left-to-right', () {
      expect(AppLanguage.ar.textDirection, TextDirection.rtl);
      expect(AppLanguage.en.textDirection, TextDirection.ltr);
      // Franco is Arabic written in Latin script, so it stays LTR.
      expect(AppLanguage.franco.textDirection, TextDirection.ltr);
    });

    test('Franco is written, never chosen', () {
      // Franco has no standard orthography, so it is not offered as an
      // interface language - a resident gets a Franco answer by writing Franco.
      expect(AppLanguage.uiChoices, [AppLanguage.en, AppLanguage.ar]);
      expect(AppLanguage.uiChoices.contains(AppLanguage.franco), isFalse);
      // It stays in the enum: the backend still labels answers "franco".
      expect(AppLanguage.values.contains(AppLanguage.franco), isTrue);
    });

    test('an answer is laid out in its own direction', () {
      // An Arabic interface can receive a Franco or English answer, and Latin
      // script laid out right-to-left is unreadable.
      expect(AppLanguage.directionFor('ar'), TextDirection.rtl);
      expect(AppLanguage.directionFor('franco'), TextDirection.ltr);
      expect(AppLanguage.directionFor('en'), TextDirection.ltr);
    });

    test('every language resolves distinct UI strings', () {
      final en = const S(AppLanguage.en).violations;
      final ar = const S(AppLanguage.ar).violations;
      final franco = const S(AppLanguage.franco).violations;

      expect({en, ar, franco}.length, 3, reason: 'each language differs');
      expect(ar, 'الغرامات');
    });
  });

  group('chat answer', () {
    test('surfaces low confidence and escalation', () {
      final answer = ChatAnswer.fromJson({
        'answer': 'I could not verify this.',
        'language': 'en',
        'detected_language': 'en',
        'intent': 'policy_question',
        'confidence': 0.1,
        'confidence_band': 'low',
        'needs_clarification': false,
        'escalated': true,
        'ticket_id': 'TKT-20260818-ABC123',
        'sources': [],
      });

      expect(answer.isLowConfidence, isTrue);
      expect(answer.escalated, isTrue);
      expect(answer.ticketId, 'TKT-20260818-ABC123');
    });
  });
}
