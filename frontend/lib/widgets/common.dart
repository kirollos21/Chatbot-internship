import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';

/// Standard async body: spinner, typed error with retry, empty state, content.
class AsyncBody<T> extends StatelessWidget {
  const AsyncBody({
    super.key,
    required this.future,
    required this.builder,
    required this.onRetry,
    this.isEmpty,
  });

  final Future<T> future;
  final Widget Function(BuildContext, T) builder;
  final VoidCallback onRetry;
  final bool Function(T)? isEmpty;

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return FutureBuilder<T>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          final error = snapshot.error;
          final message = error is ApiException && error.isOffline
              ? s.offline
              : '$error';
          return _Message(
            icon: Icons.cloud_off,
            text: message,
            actionLabel: s.retry,
            onAction: onRetry,
          );
        }
        final data = snapshot.data as T;
        if (isEmpty?.call(data) ?? false) {
          return _Message(icon: Icons.search_off, text: s.nothingFound);
        }
        return builder(context, data);
      },
    );
  }
}

class _Message extends StatelessWidget {
  const _Message({
    required this.icon,
    required this.text,
    this.actionLabel,
    this.onAction,
  });

  final IconData icon;
  final String text;
  final String? actionLabel;
  final VoidCallback? onAction;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 40, color: Theme.of(context).colorScheme.outline),
            const SizedBox(height: 12),
            Text(text, textAlign: TextAlign.center),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

/// Renders a value the backend has marked as not configured.
///
/// Deliberately shows the backend's own message rather than inventing a
/// placeholder: a resident must never see `XXXXXXXXXX` or a plausible-looking
/// fake number.
class UnavailableNotice extends StatelessWidget {
  const UnavailableNotice({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.info_outline, size: 16, color: scheme.outline),
        const SizedBox(width: 6),
        Flexible(
          child: Text(
            message,
            style: TextStyle(color: scheme.outline, fontStyle: FontStyle.italic),
          ),
        ),
      ],
    );
  }
}

/// A source reference such as `V034`, so a resident can see the answer is
/// traceable to a specific record in the regulations.
class SourceChip extends StatelessWidget {
  const SourceChip({super.key, required this.id, this.tooltip});

  final String id;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final chip = Chip(
      label: Text(id, style: const TextStyle(fontSize: 12)),
      visualDensity: VisualDensity.compact,
      materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
      side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
    );
    return tooltip == null ? chip : Tooltip(message: tooltip!, child: chip);
  }
}

class PenaltyBadge extends StatelessWidget {
  const PenaltyBadge({super.key, required this.amount, required this.currency});

  /// Pre-formatted by the model class; never recomputed here.
  final String amount;
  final String currency;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        '$amount $currency',
        style: TextStyle(
          color: scheme.onErrorContainer,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Text(
        text,
        style: Theme.of(context)
            .textTheme
            .titleSmall
            ?.copyWith(color: Theme.of(context).colorScheme.primary),
      ),
    );
  }
}
