import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Contacts directory.
///
/// Every number in the shipped dataset is still a placeholder, so the call
/// button is disabled and the backend's "not configured" message is shown
/// instead. The one thing this screen must never do is render a masked value
/// like `XXXXXXXXXX` as though it were dialable.
class ContactsScreen extends StatefulWidget {
  const ContactsScreen({super.key});

  @override
  State<ContactsScreen> createState() => _ContactsScreenState();
}

class _ContactsScreenState extends State<ContactsScreen> {
  late Future<List<Contact>> _future;
  String? _loadedFor;

  /// Keyed on the language the request sends, so switching language refetches
  /// the directory. See [AppScope.of] for why this is not in `initState`.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final key = AppScope.of(context).contentLanguage;
    if (key == _loadedFor) return;
    _loadedFor = key;
    _future = _load();
  }

  Future<List<Contact>> _load() {
    final state = AppScope.of(context);
    return state.api.contacts(language: state.contentLanguage);
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
    final scheme = Theme.of(context).colorScheme;

    return AsyncBody<List<Contact>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      builder: (context, contacts) => ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: contacts.length,
        itemBuilder: (context, i) {
          final contact = contacts[i];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
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
                        Text(
                          contact.name(language),
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 4),
                        if (contact.hasPhone)
                          Text(contact.phone!,
                              style: Theme.of(context).textTheme.bodyMedium)
                        else
                          UnavailableNotice(
                            message: contact.message ?? s.notConfigured,
                          ),
                        if (contact.hours != null &&
                            contact.hours!.isNotEmpty) ...[
                          const SizedBox(height: 4),
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
                    tooltip: contact.hasPhone ? contact.phone : s.notConfigured,
                    onPressed: contact.hasPhone ? () {} : null,
                  ),
                  SourceChip(id: contact.id),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  IconData _iconFor(String role) => switch (role) {
        'security' => Icons.shield_outlined,
        'maintenance' => Icons.build_outlined,
        'emergency' => Icons.emergency_outlined,
        'community_management' => Icons.apartment_outlined,
        'beach_office' => Icons.beach_access_outlined,
        _ => Icons.contact_phone_outlined,
      };
}
