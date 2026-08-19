import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Facilities directory.
///
/// Palm Hills has not supplied real locations or hours yet, so most records are
/// incomplete. Rather than inventing plausible values, an unconfigured field is
/// shown as the backend's explicit "not published yet" notice. Where hours *do*
/// exist they are traceable — `hours_source` names the rule they came from.
class FacilitiesScreen extends StatefulWidget {
  const FacilitiesScreen({super.key});

  @override
  State<FacilitiesScreen> createState() => _FacilitiesScreenState();
}

class _FacilitiesScreenState extends State<FacilitiesScreen> {
  late Future<List<Facility>> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<List<Facility>> _load() {
    final state = AppScope.of(context);
    return state.api
        .facilities(compound: state.compound, language: state.contentLanguage);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final language = state.contentLanguage;

    return AsyncBody<List<Facility>>(
      future: _future,
      onRetry: _reload,
      isEmpty: (list) => list.isEmpty,
      builder: (context, facilities) => ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: facilities.length,
        itemBuilder: (context, i) {
          final facility = facilities[i];
          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(_iconFor(facility.facilityType),
                          color: Theme.of(context).colorScheme.primary),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          facility.name(language),
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                      ),
                      SourceChip(id: facility.id),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Hours: real value, or an honest notice. Never a guess.
                  if (facility.hasHours)
                    Row(
                      children: [
                        const Icon(Icons.schedule, size: 16),
                        const SizedBox(width: 6),
                        Text(facility.hours!),
                        if (facility.hoursSource != null) ...[
                          const SizedBox(width: 8),
                          SourceChip(
                            id: facility.hoursSource!.replaceAll('policy:', ''),
                            tooltip: 'Hours defined by this rule',
                          ),
                        ],
                      ],
                    )
                  else
                    UnavailableNotice(message: s.hoursNotConfigured),

                  if (facility.locationNote != null &&
                      facility.locationNote!.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        const Icon(Icons.place_outlined, size: 16),
                        const SizedBox(width: 6),
                        Expanded(child: Text(facility.locationNote!)),
                      ],
                    ),
                  ] else if (!facility.isConfigured &&
                      facility.message != null) ...[
                    const SizedBox(height: 8),
                    UnavailableNotice(message: facility.message!),
                  ],

                  if (facility.restrictions.isNotEmpty) ...[
                    const Divider(height: 24),
                    for (final restriction in facility.restrictions)
                      Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Row(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Padding(
                              padding: EdgeInsets.only(top: 3),
                              child: Icon(Icons.circle, size: 6),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                restriction,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            ),
                          ],
                        ),
                      ),
                  ],
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  IconData _iconFor(String type) => switch (type) {
        'swimming_pool' => Icons.pool,
        'playground' => Icons.child_care,
        'gym_sports' => Icons.fitness_center,
        'beach' => Icons.beach_access,
        _ => Icons.place,
      };
}
