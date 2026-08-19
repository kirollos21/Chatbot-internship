import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Fines browser.
///
/// The penalty comes straight from `Violation.penaltyEgp` and is only given
/// thousands separators. Nothing here rounds it, converts it, or derives an
/// amount for a violation that has none.
class ViolationsScreen extends StatefulWidget {
  const ViolationsScreen({super.key});

  @override
  State<ViolationsScreen> createState() => _ViolationsScreenState();
}

class _ViolationsScreenState extends State<ViolationsScreen> {
  late Future<(List<Category>, List<Violation>)> _future;
  String? _categoryId;
  String _query = '';
  String? _loadedFor;

  /// Keyed on the compound: a fine can differ by compound, so changing it must
  /// refetch. See [AppScope.of] for why this is not in `initState`.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final key = AppScope.of(context).compound ?? '';
    if (key == _loadedFor) return;
    _loadedFor = key;
    _future = _load();
  }

  Future<(List<Category>, List<Violation>)> _load() async {
    final state = AppScope.of(context);
    final results = await Future.wait([
      state.api.categories(),
      state.api.violations(compound: state.compound),
    ]);
    return (results[0] as List<Category>, results[1] as List<Violation>);
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

    return AsyncBody<(List<Category>, List<Violation>)>(
      future: _future,
      onRetry: _reload,
      builder: (context, data) {
        final (categories, violations) = data;
        final filtered = violations.where((v) {
          if (_categoryId != null && v.categoryId != _categoryId) return false;
          if (_query.isEmpty) return true;
          final needle = _query.toLowerCase();
          return v.text(language).toLowerCase().contains(needle) ||
              v.id.toLowerCase().contains(needle);
        }).toList();

        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                children: [
                  TextField(
                    onChanged: (v) => setState(() => _query = v),
                    decoration: InputDecoration(
                      hintText: s.search,
                      prefixIcon: const Icon(Icons.search),
                      isDense: true,
                    ),
                  ),
                  const SizedBox(height: 10),
                  SizedBox(
                    height: 38,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      children: [
                        Padding(
                          padding: const EdgeInsetsDirectional.only(end: 8),
                          child: ChoiceChip(
                            label: Text(s.all),
                            selected: _categoryId == null,
                            onSelected: (_) =>
                                setState(() => _categoryId = null),
                          ),
                        ),
                        for (final category in categories)
                          Padding(
                            padding: const EdgeInsetsDirectional.only(end: 8),
                            child: ChoiceChip(
                              label: Text(category.label(language)),
                              selected: _categoryId == category.id,
                              onSelected: (_) =>
                                  setState(() => _categoryId = category.id),
                            ),
                          ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            Expanded(
              child: filtered.isEmpty
                  ? Center(child: Text(s.nothingFound))
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      itemCount: filtered.length,
                      itemBuilder: (context, i) {
                        final violation = filtered[i];
                        return Card(
                          margin: const EdgeInsets.only(bottom: 10),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Expanded(
                                      child: Text(
                                        violation.text(language),
                                        style: const TextStyle(
                                            fontWeight: FontWeight.w500),
                                      ),
                                    ),
                                    const SizedBox(width: 10),
                                    PenaltyBadge(
                                      amount: violation.penaltyFormatted,
                                      currency: s.egp,
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 10),
                                Text(
                                  '${s.action}: ${violation.action(language)}',
                                  style: Theme.of(context).textTheme.bodySmall,
                                ),
                                const SizedBox(height: 10),
                                Wrap(
                                  spacing: 6,
                                  runSpacing: 6,
                                  children: [
                                    SourceChip(id: violation.id),
                                    for (final ruleId
                                        in violation.relatedPolicyIds)
                                      SourceChip(id: ruleId),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }
}
