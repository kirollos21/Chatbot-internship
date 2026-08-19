/// The location picker: choose a Palm Hills project, never type one.
///
/// Typing was worse than merely inconvenient. The backend scopes rules and
/// facilities by a fixed set of tokens, so free text almost never matched one —
/// "Hacienda Bay" typed by hand scoped nothing, and a North Coast resident
/// silently lost the beach rules that apply to them. Selecting from the served
/// list means the value always means something.
///
/// The list comes from `GET /api/v1/projects`, grouped by region, so it stays
/// correctable without an app release.
library;

import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'common.dart';

/// Opens the picker and applies the choice. Returns true when something changed.
Future<bool> selectProject(BuildContext context) async {
  final state = AppScope.of(context);
  final choice = await showModalBottomSheet<_Choice>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.white,
    shape: const RoundedRectangleBorder(
      borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
    ),
    builder: (_) => const _ProjectSheet(),
  );

  if (choice == null) return false;
  state.setProject(choice.project);
  return true;
}

/// Wraps the result so "cleared" is distinguishable from "dismissed": both carry
/// a null project, but only one of them should be applied.
class _Choice {
  const _Choice(this.project);
  final Project? project;
}

class _ProjectSheet extends StatefulWidget {
  const _ProjectSheet();

  @override
  State<_ProjectSheet> createState() => _ProjectSheetState();
}

class _ProjectSheetState extends State<_ProjectSheet> {
  late Future<List<Project>> _future;
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    _future = AppScope.of(context).api.projects();
  }

  Future<void> _reload() async {
    final future = AppScope.of(context).api.projects();
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
    final selectedId = state.project?.id;

    return SafeArea(
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxHeight: MediaQuery.sizeOf(context).height * 0.82,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 12, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(s.chooseProject,
                            style: Theme.of(context).textTheme.titleLarge),
                        const SizedBox(height: 4),
                        Text(s.chooseProjectHint,
                            style: Theme.of(context).textTheme.bodySmall),
                      ],
                    ),
                  ),
                  IconButton(
                    icon: const Icon(Icons.close),
                    color: PalmHills.inkSoft,
                    onPressed: () => Navigator.pop(context),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
            Expanded(
              child: AsyncBody<List<Project>>(
                future: _future,
                onRetry: _reload,
                isEmpty: (projects) => projects.isEmpty,
                builder: (context, projects) {
                  final rows = _rows(projects, language);
                  return ListView.builder(
                    padding: const EdgeInsets.only(bottom: 12),
                    itemCount: rows.length + 1,
                    itemBuilder: (context, i) {
                      if (i == 0) {
                        // Clearing is a real choice: with no project selected the
                        // assistant answers from community-wide rules only and
                        // says so, rather than guessing a location.
                        return _ProjectTile(
                          label: s.notSet,
                          detail: s.noProjectHint,
                          selected: selectedId == null,
                          onTap: () =>
                              Navigator.pop(context, const _Choice(null)),
                        );
                      }
                      final row = rows[i - 1];
                      if (row.header != null) {
                        return SectionHeader(row.header!);
                      }
                      final project = row.project!;
                      return _ProjectTile(
                        label: project.name(language),
                        selected: project.id == selectedId,
                        onTap: () => Navigator.pop(context, _Choice(project)),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Flattens the list into headers and projects, keeping the backend's order —
  /// it groups by region deliberately and the picker should not re-sort it.
  List<_Row> _rows(List<Project> projects, String language) {
    final rows = <_Row>[];
    String? region;
    for (final project in projects) {
      if (project.region != region) {
        region = project.region;
        rows.add(_Row.header(project.regionLabel(language)));
      }
      rows.add(_Row.project(project));
    }
    return rows;
  }
}

class _Row {
  const _Row.header(this.header) : project = null;
  const _Row.project(this.project) : header = null;
  final String? header;
  final Project? project;
}

class _ProjectTile extends StatelessWidget {
  const _ProjectTile({
    required this.label,
    required this.selected,
    required this.onTap,
    this.detail,
  });

  final String label;
  final String? detail;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      onTap: onTap,
      // Compact locally rather than in the theme: 23 projects in a sheet need
      // tighter rows than a single settings row on Home does.
      visualDensity: VisualDensity.compact,
      minVerticalPadding: 4,
      title: Text(
        label,
        style: TextStyle(
          fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
          color: selected ? PalmHills.brand : PalmHills.ink,
        ),
      ),
      subtitle: detail == null ? null : Text(detail!),
      trailing: selected
          ? const Icon(Icons.check_circle, color: PalmHills.brand)
          : const Icon(Icons.circle_outlined, color: PalmHills.line),
    );
  }
}
