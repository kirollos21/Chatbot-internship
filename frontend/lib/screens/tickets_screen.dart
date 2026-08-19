import 'package:flutter/material.dart';

import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Support tickets and submitted reports.
///
/// Tickets appear here when the assistant could not verify an answer and
/// escalated to Community Management — the resident can see the request exists
/// and where it stands.
class TicketsScreen extends StatefulWidget {
  const TicketsScreen({super.key});

  @override
  State<TicketsScreen> createState() => _TicketsScreenState();
}

class _TicketsScreenState extends State<TicketsScreen> {
  late Future<(List<Ticket>, List<ViolationReport>)> _future;

  @override
  void initState() {
    super.initState();
    _future = _load();
  }

  Future<(List<Ticket>, List<ViolationReport>)> _load() async {
    final api = AppScope.of(context).api;
    final results = await Future.wait([api.tickets(), api.reports()]);
    return (results[0] as List<Ticket>, results[1] as List<ViolationReport>);
  }

  void _reload() => setState(() => _future = _load());

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;

    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: AsyncBody<(List<Ticket>, List<ViolationReport>)>(
        future: _future,
        onRetry: _reload,
        builder: (context, data) {
          final (tickets, reports) = data;
          if (tickets.isEmpty && reports.isEmpty) {
            return ListView(
              children: [
                const SizedBox(height: 120),
                Center(child: Text(s.noTickets)),
              ],
            );
          }

          return ListView(
            padding: const EdgeInsets.only(bottom: 16),
            children: [
              if (tickets.isNotEmpty) SectionHeader(s.myRequests),
              for (final ticket in tickets)
                Card(
                  margin: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                  child: ListTile(
                    leading: const Icon(Icons.support_agent),
                    title: Text(ticket.ticketId),
                    subtitle: Text(ticket.assignedTeam ?? ticket.reason),
                    trailing: _StatusPill(label: s.statusLabel(ticket.status)),
                  ),
                ),
              if (reports.isNotEmpty) SectionHeader(s.reportTitle),
              for (final report in reports)
                Card(
                  margin: const EdgeInsets.fromLTRB(16, 0, 16, 10),
                  child: ListTile(
                    leading: const Icon(Icons.flag_outlined),
                    title: Text(report.reportId),
                    subtitle: Text(
                      report.description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: _StatusPill(label: s.statusLabel(report.status)),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: scheme.secondaryContainer,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        label,
        style: TextStyle(fontSize: 12, color: scheme.onSecondaryContainer),
      ),
    );
  }
}
