import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Contacts directory, scoped to the resident's project.
///
/// Three states, and the difference between them matters:
///
/// * **configured** — a real number confirmed by Community Management.
/// * **unverified** — a number Palm Hills lists publicly that Community
///   Management has not confirmed. Shown and dialable, but always with the
///   caveat attached; a resident deserves to know which of the two they have.
/// * **not configured** — the shipped dataset's placeholders. The call button
///   is disabled and the backend's own message is shown.
///
/// The one thing this screen must never do is render a masked value like
/// `XXXXXXXXXX` as though it were dialable.
class ContactsScreen extends StatefulWidget {
  const ContactsScreen({super.key});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  late Future<List<Contact>> _future;
  String? _loadedFor;

  /// Keyed on language *and* project: the numbers a resident should call
  /// depend on where they live, so changing project refetches the directory.
  /// See [AppScope.of] for why this is not in `initState`.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final state = AppScope.of(context);
    final key = '${state.contentLanguage}|${state.compound ?? ''}';
    if (key == _loadedFor) return;
    _loadedFor = key;
    _future = _load();
  }

  Future<List<Contact>> _load() {
    final state = AppScope.of(context);
    return state.api.contacts(
      compound: state.compound,
      language: state.contentLanguage,
    );
  }

  /// Block body, not `setState(() => _future = _load())` — see
  /// `policies_screen.dart` for what the arrow form breaks.
  Future<void> _reload() async {
    final future = _load();
    setState(() {
      _future = future;
    });
    try {
      await future;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final language = state.contentLanguage;

    return AsyncBody<List<Contact>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      builder: (context, contacts) => ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: contacts.length,
        itemBuilder: (context, i) => _ContactCard(
          contact: contacts[i],
          language: language,
          notConfigured: s.notConfigured,
        ),
      ),
    );
  }
}

class _ContactCard extends StatelessWidget {
  const _ContactCard({
    required this.contact,
    required this.language,
    required this.notConfigured,
  });

  final Contact contact;
  final String language;
  final String notConfigured;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  backgroundColor: scheme.secondaryContainer,
                  child: Icon(_iconFor(contact.role),
                      color: scheme.onSecondaryContainer),
                ),
                const SizedBox(width: 14),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(contact.name(language),
                          style: Theme.of(context).textTheme.titleSmall),
                      if (contact.hasPhone) ...[
                        const SizedBox(height: 4),
                        SelectableText(
                          contact.phone!,
                          style: Theme.of(context)
                              .textTheme
                              .bodyLarge
                              ?.copyWith(fontWeight: FontWeight.w600),
                        ),
                      ],
                      if (contact.hours != null && contact.hours!.isNotEmpty) ...[
                        const SizedBox(height: 2),
                        Text(contact.hours!,
                            style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ],
                  ),
                ),
                // Disabled until a real number exists — a dead call button is
                // better than one that dials nothing.
                IconButton(
                  icon: const Icon(Icons.call),
                  tooltip: contact.hasPhone ? contact.phone : notConfigured,
                  onPressed: contact.hasPhone ? () {} : null,
                ),
                // Only the dataset's own records carry a traceable id worth
                // quoting back. A reference contact's id means nothing to a
                // resident, so it is not shown to them.
                if (contact.source == null) SourceChip(id: contact.id),
              ],
            ),
            // Full width, below the row: whether a number is confirmed is the
            // most important thing on this card after the number itself.
            if (contact.message != null) ...[
              const SizedBox(height: 10),
              UnavailableNotice(message: contact.message!),
            ] else if (!contact.hasPhone) ...[
              const SizedBox(height: 10),
              UnavailableNotice(message: notConfigured),
            ],
          ],
        ),
      ),
    );
  }

  IconData _iconFor(String role) => switch (role) {
        'security' => Icons.shield_outlined,
        'maintenance' => Icons.build_outlined,
        'emergency' => Icons.emergency_outlined,
        'community_management' => Icons.apartment_outlined,
        'beach_office' => Icons.beach_access_outlined,
        'customer_care' => Icons.support_agent_outlined,
        'community_office' => Icons.business_outlined,
        _ => Icons.contact_phone_outlined,
      };
}
