import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/theme.dart';

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
            Container(
              width: 60,
              height: 60,
              decoration: BoxDecoration(
                color: PalmHills.brandSoft,
                borderRadius: BorderRadius.circular(18),
              ),
              child: Icon(icon, size: 27, color: PalmHills.brand),
            ),
            const SizedBox(height: 16),
            Text(
              text,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            if (actionLabel != null && onAction != null) ...[
              const SizedBox(height: 18),
              FilledButton(onPressed: onAction, child: Text(actionLabel!)),
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
    // Monospace-ish and boxed: a record id is a reference a resident can quote
    // back to Community Management, so it should look like an identifier rather
    // than a decorative tag.
    final chip = Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
      decoration: BoxDecoration(
        color: PalmHills.sandDim,
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: PalmHills.line),
      ),
      child: Text(
        id,
        style: const TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: PalmHills.brandDeep,
        ),
      ),
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
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: PalmHills.brandSoft,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: PalmHills.brand.withValues(alpha: 0.22)),
      ),
      child: Text(
        '$amount $currency',
        style: const TextStyle(
          color: PalmHills.brandDeep,
          fontWeight: FontWeight.w700,
          fontSize: 13.5,
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
      padding: const EdgeInsets.fromLTRB(16, 22, 16, 10),
      child: Row(
        children: [
          Container(
            width: 3,
            height: 15,
            decoration: BoxDecoration(
              color: PalmHills.brand,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 9),
          Text(
            text,
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(color: PalmHills.brandDeep),
          ),
        ],
      ),
    );
  }
}
