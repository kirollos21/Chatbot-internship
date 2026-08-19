import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/strings.dart';
import '../core/theme.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// The assistant conversation.
///
/// Two things this screen is careful about:
///
/// * It renders `answer` exactly as the backend produced it. No client-side
///   summarising, truncation or reformatting — the backend already ran the
///   integrity guard over that text, and editing it here would step outside
///   what was verified.
/// * A low-confidence or escalated answer is visibly marked as such rather than
///   being dressed up to look like a confident one.
class AssistantScreen extends StatefulWidget {
  const AssistantScreen({super.key});

  @override
  State<AssistantScreen> createState() => _AssistantScreenState();
}

class _AssistantScreenState extends State<AssistantScreen> {
  final _controller = TextEditingController();
  final _scroll = ScrollController();
  final List<_Turn> _turns = [];
  bool _busy = false;

  @override
  void dispose() {
    _controller.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _busy) return;

    final state = AppScope.of(context);
    setState(() {
      _turns.add(_Turn.user(text));
      _busy = true;
      _controller.clear();
    });
    _scrollToEnd();

    try {
      // No `language`: the answer follows the language the resident wrote in.
      // Writing Franco is how you get a Franco answer - it is not a setting.
      final answer = await state.api.ask(
        message: text,
        compound: state.compound,
        phase: state.phase,
      );
      if (!mounted) return;
      setState(() => _turns.add(_Turn.assistant(answer)));
    } on ApiException catch (e) {
      if (!mounted) return;
      final message = e.isOffline ? state.strings.offline : e.message;
      setState(() => _turns.add(_Turn.error(message)));
    } finally {
      if (mounted) setState(() => _busy = false);
      _scrollToEnd();
    }
  }

  void _scrollToEnd() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 250),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;

    return Column(
      children: [
        Expanded(
          child: _turns.isEmpty
              ? _EmptyState(onPick: (q) {
                  _controller.text = q;
                  _send();
                })
              : ListView.builder(
                  controller: _scroll,
                  padding: const EdgeInsets.all(16),
                  itemCount: _turns.length,
                  itemBuilder: (context, i) => _TurnView(turn: _turns[i]),
                ),
        ),
        if (_busy)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                const SizedBox(
                  width: 14,
                  height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2),
                ),
                const SizedBox(width: 10),
                Text(s.thinking,
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            ),
          ),
        Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            border: Border(top: BorderSide(color: PalmHills.line)),
          ),
          child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  // The field follows what is being typed, not the interface: a
                  // resident writing Franco in an Arabic app would otherwise
                  // watch their own punctuation jump to the front of the line.
                  child: ValueListenableBuilder<TextEditingValue>(
                    valueListenable: _controller,
                    builder: (context, value, _) => TextField(
                      controller: _controller,
                      minLines: 1,
                      maxLines: 4,
                      textDirection: value.text.isEmpty
                          ? null
                          : _directionOfText(value.text),
                      textInputAction: TextInputAction.send,
                      onSubmitted: (_) => _send(),
                      decoration: InputDecoration(hintText: s.askPlaceholder),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                FilledButton(
                  onPressed: _busy ? null : _send,
                  child: Text(s.send),
                ),
              ],
            ),
          ),
          ),
        ),
      ],
    );
  }
}

/// Latin script — English or Franco — must stay left-to-right even when the
/// interface is Arabic. Laid out right-to-left, bidi reordering throws the
/// trailing punctuation to the front ("?momken a3mel..."), which looks broken.
///
/// Answers use `AppLanguage.directionFor` instead: the backend states what
/// language it wrote, which beats guessing from the characters.
final _arabicScript = RegExp(r'[؀-ۿ]');

TextDirection _directionOfText(String text) =>
    _arabicScript.hasMatch(text) ? TextDirection.rtl : TextDirection.ltr;

class _Turn {
  _Turn.user(this.text)
      : isUser = true,
        answer = null,
        error = null;
  _Turn.assistant(this.answer)
      : isUser = false,
        text = null,
        error = null;
  _Turn.error(this.error)
      : isUser = false,
        text = null,
        answer = null;

  final bool isUser;
  final String? text;
  final ChatAnswer? answer;
  final String? error;
}

class _TurnView extends StatelessWidget {
  const _TurnView({required this.turn});

  final _Turn turn;

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final scheme = Theme.of(context).colorScheme;

    if (turn.isUser) {
      return Align(
        alignment: AlignmentDirectional.centerEnd,
        child: Directionality(
          textDirection: _directionOfText(turn.text!),
          child: Container(
          margin: const EdgeInsets.only(bottom: 14),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          constraints: const BoxConstraints(maxWidth: 520),
          decoration: const BoxDecoration(
            gradient: PalmHills.heroGradient,
            borderRadius: BorderRadius.only(
              topLeft: Radius.circular(18),
              topRight: Radius.circular(18),
              bottomLeft: Radius.circular(18),
              bottomRight: Radius.circular(6),
            ),
          ),
          child: Text(
            turn.text!,
            style: const TextStyle(color: Colors.white, height: 1.45),
          ),
        ),
        ),
      );
    }

    if (turn.error != null) {
      return Align(
        alignment: AlignmentDirectional.centerStart,
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: scheme.errorContainer,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(turn.error!,
              style: TextStyle(color: scheme.onErrorContainer)),
        ),
      );
    }

    final answer = turn.answer!;
    // The answer carries its own direction. An Arabic interface can receive a
    // Franco or English answer, and Latin script laid out right-to-left is
    // unreadable, so the bubble follows the answer rather than the interface.
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Directionality(
        textDirection: AppLanguage.directionFor(answer.language),
        child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(16),
        constraints: const BoxConstraints(maxWidth: 640),
        decoration: BoxDecoration(
          color: Colors.white,
          border: Border.all(color: PalmHills.line),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(18),
            topRight: Radius.circular(18),
            bottomLeft: Radius.circular(6),
            bottomRight: Radius.circular(18),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (answer.isLowConfidence || answer.needsClarification)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    if (answer.isLowConfidence)
                      _Flag(
                        icon: Icons.help_outline,
                        label: s.lowConfidence,
                        color: scheme.tertiary,
                      ),
                    if (answer.needsClarification)
                      _Flag(
                        icon: Icons.location_city_outlined,
                        label: s.needsCompound,
                        // Amber, not the brand red: "tell me your project" is a
                        // prompt, and red would read as a failure.
                        color: PalmHills.amber,
                      ),
                  ],
                ),
              ),

            // Verbatim backend text. Do not post-process.
            SelectableText(answer.answer),

            if (answer.escalated) ...[
              const SizedBox(height: 12),
              Row(
                children: [
                  Icon(Icons.support_agent, size: 18, color: scheme.primary),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      answer.ticketId == null
                          ? s.escalated
                          : '${s.escalated} · ${s.ticketRef} ${answer.ticketId}',
                      style: TextStyle(color: scheme.primary),
                    ),
                  ),
                ],
              ),
            ],

            if (answer.sources.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text('${s.sources}:',
                  style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final source in answer.sources)
                    SourceChip(id: source.id, tooltip: source.label),
                ],
              ),
            ],
          ],
        ),
        ),
      ),
    );
  }
}

/// A tappable example question. Latin samples stay left-to-right even when the
/// interface is Arabic, which is what makes the Franco example legible.
class _SampleChip extends StatelessWidget {
  const _SampleChip({required this.text, required this.onTap});

  final String text;
  final VoidCallback onTap;

  static final _arabic = RegExp(r'[\u0600-\u06FF]');

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection:
          _arabic.hasMatch(text) ? TextDirection.rtl : TextDirection.ltr,
      child: Material(
        color: Colors.white,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(30),
          side: const BorderSide(color: PalmHills.line),
        ),
        child: InkWell(
          borderRadius: BorderRadius.circular(30),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
            child: Text(
              text,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: PalmHills.brandDeep,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Flag extends StatelessWidget {
  const _Flag({required this.icon, required this.label, required this.color});

  final IconData icon;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 12, color: color)),
        ],
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.onPick});

  final void Function(String) onPick;

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;

    // Two samples in the interface language and one in Franco. The Franco one
    // is the point: Franco is no longer in the language menu, so an example a
    // resident can tap is how they find out it is understood at all.
    final samples = switch (state.language.code) {
      'ar' => [
          'ايه غرامة الركنة على الزرع؟',
          'هل يمكن وضع برجولة في الحديقة؟',
          'fe kam ghrama 3ala el parking 3al zar3?',
        ],
      _ => [
          'What is the fine for parking on the grass?',
          'Can I take my dog to the beach?',
          'momken a3mel pergola fel gnena?',
        ],
    };

    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 62,
              height: 62,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                gradient: PalmHills.heroGradient,
              ),
              child: const Icon(Icons.forum_outlined,
                  size: 28, color: Colors.white),
            ),
            const SizedBox(height: 18),
            Text(s.homeGreeting,
                style: Theme.of(context).textTheme.titleLarge,
                textAlign: TextAlign.center),
            const SizedBox(height: 8),
            Text(s.writeAnyLanguage,
                style: Theme.of(context).textTheme.bodySmall,
                textAlign: TextAlign.center),
            const SizedBox(height: 22),
            for (final sample in samples)
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: _SampleChip(text: sample, onTap: () => onPick(sample)),
              ),
          ],
        ),
      ),
    );
  }
}
