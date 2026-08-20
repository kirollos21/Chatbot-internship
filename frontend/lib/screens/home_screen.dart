import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/theme.dart';
import '../main.dart' show ShellNavigator;
import '../widgets/palm_motif.dart';
import '../widgets/project_picker.dart';
import 'assistant_screen.dart';
import 'complaints_screen.dart';
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

    final tiles = <_Tile>[
      _Tile(s.assistant, Icons.forum_outlined, PalmHills.brand,
          const AssistantScreen()),
      _Tile(s.policies, Icons.menu_book_outlined, PalmHills.brand,
          const PoliciesScreen()),
      _Tile(s.violations, Icons.gavel_outlined, PalmHills.brand,
          const ViolationsScreen()),
      _Tile(s.facilities, Icons.pool_outlined, PalmHills.brand,
          const FacilitiesScreen()),
      _Tile(s.contacts, Icons.call_outlined, PalmHills.brand,
          const ContactsScreen()),
      _Tile(s.reportViolation, Icons.flag_outlined, PalmHills.brand,
          const ReportScreen()),
      _Tile(s.complaints, Icons.feedback_outlined, PalmHills.brand,
          const ComplaintsScreen()),
      _Tile(s.myRequests, Icons.receipt_long_outlined, PalmHills.brand,
          const TicketsScreen()),
    ];

    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
      children: [
        PalmHero(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                s.communityName,
                style: TextStyle(
                  color: Colors.white.withValues(alpha: 0.78),
                  fontSize: 12.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 1.6,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                s.homeGreeting,
                style: Theme.of(context)
                    .textTheme
                    .headlineSmall
                    ?.copyWith(color: Colors.white),
              ),
              const SizedBox(height: 10),
              // Constrained so the text never runs under the palm motif.
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 300),
                child: Text(
                  s.homeSubtitle,
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.82),
                    height: 1.45,
                  ),
                ),
              ),
              const SizedBox(height: 20),
              FilledButton.icon(
                onPressed: () => ShellNavigator.goTo(
                    context, const AssistantScreen(), s.assistant),
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.white,
                  foregroundColor: PalmHills.brandDeep,
                ),
                icon: const Icon(Icons.forum_outlined, size: 20),
                label: Text(s.askAssistant),
              ),
            ],
          ),
        ),
        const SizedBox(height: 18),
        const _CompoundCard(),
        const SizedBox(height: 22),
        Padding(
          padding: const EdgeInsetsDirectional.only(start: 4, bottom: 12),
          child: Text(s.browse,
              style: Theme.of(context).textTheme.titleSmall?.copyWith(
                    color: PalmHills.inkSoft,
                  )),
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final columns = constraints.maxWidth >= 720 ? 4 : 2;
            return GridView.count(
              crossAxisCount: columns,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.5,
              children: [
                for (final tile in tiles) _TileCard(tile: tile),
              ],
            );
          },
        ),
      ],
    );
  }
}

class _Tile {
  const _Tile(this.label, this.icon, this.accent, this.screen);
  final String label;
  final IconData icon;
  final Color accent;
  final Widget screen;
}

class _TileCard extends StatelessWidget {
  const _TileCard({required this.tile});

  final _Tile tile;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(PalmHills.radiusCard),
        onTap: () => ShellNavigator.goTo(context, tile.screen, tile.label),
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  // A wash of the tile's accent, not the accent itself: the
                  // icon has to stay the loudest thing in the card.
                  color: tile.accent.withValues(alpha: 0.10),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(tile.icon, size: 21, color: tile.accent),
              ),
              const Spacer(),
              Text(
                tile.label,
                style: Theme.of(context).textTheme.titleMedium,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Lets the resident select which Palm Hills project they live in.
///
/// This matters for correctness, not convenience: when a rule could differ by
/// project and the backend does not know which one the resident is in, it
/// declines to guess and asks. Selecting here removes that ambiguity.
///
/// Selected, never typed — see `widgets/project_picker.dart` for why free text
/// could not scope anything.
class _CompoundCard extends StatelessWidget {
  const _CompoundCard();

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final project = state.project;
    final isSet = project != null;

    return Card(
      child: ListTile(
        onTap: () => selectProject(context),
        leading: Container(
          width: 42,
          height: 42,
          decoration: BoxDecoration(
            color: PalmHills.brandSoft,
            borderRadius: BorderRadius.circular(12),
          ),
          child: const Icon(Icons.location_city_outlined,
              size: 21, color: PalmHills.brand),
        ),
        title: Text(s.compound,
            style: Theme.of(context).textTheme.titleMedium),
        subtitle: Text(
          isSet ? project.name(state.contentLanguage) : s.compoundHint,
          style: TextStyle(
            color: isSet ? PalmHills.brand : PalmHills.inkSoft,
            fontWeight: isSet ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
        trailing: const Icon(Icons.expand_more, color: PalmHills.inkSoft),
      ),
    );
  }
}
