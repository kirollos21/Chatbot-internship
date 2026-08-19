import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../main.dart' show ShellNavigator;
import 'assistant_screen.dart';
import 'contacts_screen.dart';
import 'facilities_screen.dart';
import 'policies_screen.dart';
import 'report_screen.dart';
import 'tickets_screen.dart';
import 'violations_screen.dart';

class HomeScreen extends StatelessWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final scheme = Theme.of(context).colorScheme;

    final tiles = <_Tile>[
      _Tile(s.assistant, Icons.chat_bubble_outline, const AssistantScreen()),
      _Tile(s.policies, Icons.menu_book_outlined, const PoliciesScreen()),
      _Tile(s.violations, Icons.gavel_outlined, const ViolationsScreen()),
      _Tile(s.facilities, Icons.pool_outlined, const FacilitiesScreen()),
      _Tile(s.contacts, Icons.call_outlined, const ContactsScreen()),
      _Tile(s.reportViolation, Icons.flag_outlined, const ReportScreen()),
      _Tile(s.myRequests, Icons.receipt_long_outlined, const TicketsScreen()),
    ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.homeGreeting,
                    style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 8),
                Text(s.homeSubtitle,
                    style: TextStyle(color: scheme.onSurfaceVariant)),
                const SizedBox(height: 16),
                FilledButton.icon(
                  onPressed: () => ShellNavigator.goTo(
                      context, const AssistantScreen(), s.assistant),
                  icon: const Icon(Icons.chat_bubble_outline),
                  label: Text(s.assistant),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        const _CompoundCard(),
        const SizedBox(height: 16),
        LayoutBuilder(
          builder: (context, constraints) {
            final columns = constraints.maxWidth >= 720 ? 4 : 2;
            return GridView.count(
              crossAxisCount: columns,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.25,
              children: [
                for (final tile in tiles)
                  Card(
                    child: InkWell(
                      borderRadius: BorderRadius.circular(14),
                      onTap: () =>
                          ShellNavigator.goTo(context, tile.screen, tile.label),
                      child: Padding(
                        padding: const EdgeInsets.all(12),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(tile.icon, size: 28, color: scheme.primary),
                            const SizedBox(height: 10),
                            Text(
                              tile.label,
                              textAlign: TextAlign.center,
                              style: Theme.of(context).textTheme.bodyMedium,
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _Tile {
  const _Tile(this.label, this.icon, this.screen);
  final String label;
  final IconData icon;
  final Widget screen;
}

/// Lets the resident record their compound.
///
/// This matters for correctness, not convenience: when a rule could differ by
/// compound and the backend does not know which one the resident is in, it
/// declines to guess and asks. Setting it here removes that ambiguity.
class _CompoundCard extends StatelessWidget {
  const _CompoundCard();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;

    return Card(
      child: ListTile(
        leading: const Icon(Icons.location_city_outlined),
        title: Text(s.compound),
        subtitle: Text(state.compound ?? s.compoundHint),
        trailing: const Icon(Icons.edit_outlined),
        onTap: () async {
          final controller = TextEditingController(text: state.compound ?? '');
          final value = await showDialog<String>(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(s.compound),
              content: TextField(
                controller: controller,
                autofocus: true,
                decoration: InputDecoration(hintText: s.compoundHint),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: Text(s.cancel),
                ),
                FilledButton(
                  onPressed: () => Navigator.pop(context, controller.text),
                  child: Text(s.submit),
                ),
              ],
            ),
          );
          if (value != null) state.setCompound(value);
        },
      ),
    );
  }
}
