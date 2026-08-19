import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
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
      final answer = await state.api.ask(
        message: text,
        language: state.languageCode,
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
        SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    minLines: 1,
                    maxLines: 4,
                    textInputAction: TextInputAction.send,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(hintText: s.askPlaceholder),
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: _busy ? null : _send,
                  child: Text(s.send),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}

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
        child: Container(
          margin: const EdgeInsets.only(bottom: 12),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
          constraints: const BoxConstraints(maxWidth: 520),
          decoration: BoxDecoration(
            color: scheme.primaryContainer,
            borderRadius: BorderRadius.circular(14),
          ),
          child: Text(turn.text!),
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
    return Align(
      alignment: AlignmentDirectional.centerStart,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.all(14),
        constraints: const BoxConstraints(maxWidth: 640),
        decoration: BoxDecoration(
          color: scheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(14),
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
                        color: scheme.secondary,
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

    // Suggestions are written in the selected language so a Franco speaker sees
    // Franco examples, which is also the fastest way to show the app accepts it.
    final samples = switch (state.language.code) {
      'ar' => [
          'ايه غرامة الركنة على الزرع؟',
          'هل يمكن وضع برجولة في الحديقة؟',
          'هل يسمح باصطحاب الكلب إلى الشاطئ؟',
        ],
      'franco' => [
          'fe kam ghrama 3ala el parking 3al zar3?',
          'momken a3mel pergola fel gnena?',
          'feen ra2m el maintenance?',
        ],
      _ => [
          'What is the fine for parking on the grass?',
          'Can I build a pergola in my garden?',
          'Can I take my dog to the beach?',
        ],
    };

    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.chat_bubble_outline,
                size: 44, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(s.homeGreeting,
                style: Theme.of(context).textTheme.titleMedium,
                textAlign: TextAlign.center),
            const SizedBox(height: 20),
            for (final sample in samples)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: OutlinedButton(
                  onPressed: () => onPick(sample),
                  child: Text(sample, textAlign: TextAlign.center),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
