import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

class PoliciesScreen extends StatefulWidget {
  const PoliciesScreen({super.key});

  @override
  State<PoliciesScreen> createState() => _PoliciesScreenState();
}

class _PoliciesScreenState extends State<PoliciesScreen> {
  late Future<(List<Category>, List<Policy>)> _future;
  String? _categoryId;
  String _query = '';

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<(List<Category>, List<Policy>)> _load() async {
    final api = AppScope.of(context).api;
    final compound = AppScope.of(context).compound;
    final results = await Future.wait([
      api.categories(),
      api.policies(compound: compound),
    ]);
    return (results[0] as List<Category>, results[1] as List<Policy>);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final language = state.contentLanguage;

    return AsyncBody<(List<Category>, List<Policy>)>(
      future: _future,
      onRetry: _reload,
      builder: (context, data) {
        final (categories, policies) = data;
        final filtered = policies.where((p) {
          if (_categoryId != null && p.categoryId != _categoryId) return false;
          if (_query.isEmpty) return true;
          final needle = _query.toLowerCase();
          return p.text(language).toLowerCase().contains(needle) ||
              p.id.toLowerCase().contains(needle);
        }).toList();

        return Column(
          children: [
            _FilterBar(
              categories: categories,
              selected: _categoryId,
              language: language,
              searchHint: s.search,
              allLabel: s.all,
              onCategory: (v) => setState(() => _categoryId = v),
              onSearch: (v) => setState(() => _query = v),
            ),
            Expanded(
              child: filtered.isEmpty
                  ? Center(child: Text(s.nothingFound))
                  : ListView.builder(
                      padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                      itemCount: filtered.length,
                      itemBuilder: (context, i) {
                        final policy = filtered[i];
                        return Card(
                          margin: const EdgeInsets.only(bottom: 10),
                          child: Padding(
                            padding: const EdgeInsets.all(14),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    SourceChip(id: policy.id),
                                    const Spacer(),
                                    if (policy.isDerived(language))
                                      // Honest about provenance: this wording was
                                      // translated during data preparation, not
                                      // taken from the source document.
                                      Tooltip(
                                        message: 'Translated during data preparation',
                                        child: Icon(
                                          Icons.translate,
                                          size: 16,
                                          color: Theme.of(context)
                                              .colorScheme
                                              .outline,
                                        ),
                                      ),
                                  ],
                                ),
                                const SizedBox(height: 8),
                                Text(policy.text(language)),
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

class _FilterBar extends StatelessWidget {
  const _FilterBar({
    required this.categories,
    required this.selected,
    required this.language,
    required this.searchHint,
    required this.allLabel,
    required this.onCategory,
    required this.onSearch,
  });

  final List<Category> categories;
  final String? selected;
  final String language;
  final String searchHint;
  final String allLabel;
  final ValueChanged<String?> onCategory;
  final ValueChanged<String> onSearch;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          TextField(
            onChanged: onSearch,
            decoration: InputDecoration(
              hintText: searchHint,
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
                    label: Text(allLabel),
                    selected: selected == null,
                    onSelected: (_) => onCategory(null),
                  ),
                ),
                for (final category in categories)
                  Padding(
                    padding: const EdgeInsetsDirectional.only(end: 8),
                    child: ChoiceChip(
                      label: Text(category.label(language)),
                      selected: selected == category.id,
                      onSelected: (_) => onCategory(category.id),
                    ),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
