/// Complaints: raise one, and see the ones you have raised.
///
/// Kept separate from "Report a violation" on purpose. Reporting a violation
/// accuses another resident and is governed by verification rules — a report
/// stays `reported` until staff confirm it. A complaint accuses nobody; it is
/// the resident saying something is wrong with the community or its services.
/// Merging the two would quietly turn every grievance into an allegation.
library;

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/models.dart';
import '../core/theme.dart';
import '../widgets/common.dart';

class ComplaintsScreen extends StatefulWidget {
  const ComplaintsScreen({super.key});

  @override
  State<ComplaintsScreen> createState() => _ComplaintsScreenState();
}

class _ComplaintsScreenState extends State<ComplaintsScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 2, vsync: this);

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return Column(
      children: [
        Material(
          color: Colors.white,
          child: TabBar(
            controller: _tabs,
            labelColor: PalmHills.brandDeep,
            unselectedLabelColor: PalmHills.inkSoft,
            indicatorColor: PalmHills.brand,
            tabs: [
              Tab(text: s.newComplaint),
              Tab(text: s.myComplaints),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabs,
            children: [
              _ComplaintForm(onFiled: () => _tabs.animateTo(1)),
              const _ComplaintList(),
            ],
          ),
        ),
      ],
    );
  }
}

// --------------------------------------------------------------------- form

class _ComplaintForm extends StatefulWidget {
  const _ComplaintForm({required this.onFiled});

  final VoidCallback onFiled;

  @override
  State<_ComplaintForm> createState() => _ComplaintFormState();
}

class _ComplaintFormState extends State<_ComplaintForm> {
  final _subject = TextEditingController();
  final _description = TextEditingController();
  final _location = TextEditingController();
  final _phone = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  Future<List<ComplaintCategory>>? _categories;
  ComplaintCategory? _category;
  bool _busy = false;
  Complaint? _filed;

  /// Categories are fetched once; they do not depend on language or project —
  /// each carries both labels. See [AppScope.of] for why not `initState`.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _categories ??= AppScope.of(context).api.complaintCategories();
  }

  @override
  void dispose() {
    _subject.dispose();
    _description.dispose();
    _location.dispose();
    _phone.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false) || _busy) return;
    if (_category == null) return;

    final state = AppScope.of(context);
    setState(() => _busy = true);
    try {
      final complaint = await state.api.createComplaint(
        category: _category!.id,
        subject: _subject.text.trim(),
        description: _description.text.trim(),
        locationText: _location.text.trim(),
        contactPhone: _phone.text.trim(),
        compound: state.compound,
        phase: state.phase,
      );
      if (!mounted) return;
      setState(() => _filed = complaint);
      _subject.clear();
      _description.clear();
      _location.clear();
      _phone.clear();
      widget.onFiled();
    } on ApiException catch (e) {
      if (!mounted) return;
      final message = e.isOffline ? state.strings.offline : e.message;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text(message)));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = AppScope.of(context);
    final s = state.strings;
    final language = state.contentLanguage;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (_filed != null) ...[
          _FiledBanner(complaint: _filed!),
          const SizedBox(height: 16),
        ],
        Text(s.complaintIntro, style: Theme.of(context).textTheme.bodyMedium),
        const SizedBox(height: 20),
        Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              FutureBuilder<List<ComplaintCategory>>(
                future: _categories,
                builder: (context, snapshot) {
                  final categories =
                      snapshot.data ?? const <ComplaintCategory>[];
                  return DropdownButtonFormField<String>(
                    initialValue: _category?.id,
                    isExpanded: true,
                    decoration:
                        InputDecoration(labelText: s.complaintCategory),
                    validator: (v) => v == null ? s.required : null,
                    items: [
                      for (final category in categories)
                        DropdownMenuItem(
                          value: category.id,
                          child: Text(
                            category.label(language),
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                    ],
                    onChanged: (v) => setState(() => _category =
                        categories.firstWhere((c) => c.id == v)),
                  );
                },
              ),

              // Filing a form for something in progress is the wrong channel,
              // and the resident should be told before they type it all out.
              if (_category?.urgent ?? false) ...[
                const SizedBox(height: 12),
                _UrgentNotice(text: s.complaintUrgentCall),
              ],

              const SizedBox(height: 16),
              TextFormField(
                controller: _subject,
                maxLength: 120,
                decoration: InputDecoration(
                  labelText: s.complaintSubject,
                  hintText: s.complaintSubjectHint,
                ),
                validator: (v) =>
                    (v == null || v.trim().length < 3) ? s.required : null,
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _description,
                minLines: 4,
                maxLines: 8,
                maxLength: 4000,
                decoration: InputDecoration(labelText: s.complaintDetails),
                validator: (v) =>
                    (v == null || v.trim().length < 5) ? s.required : null,
              ),
              const SizedBox(height: 8),
              TextFormField(
                controller: _location,
                decoration: InputDecoration(labelText: s.complaintWhere),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _phone,
                keyboardType: TextInputType.phone,
                decoration: InputDecoration(labelText: s.complaintPhone),
              ),
              const SizedBox(height: 20),
              FilledButton(
                onPressed: _busy ? null : _submit,
                child: Text(_busy ? s.thinking : s.submitComplaint),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _UrgentNotice extends StatelessWidget {
  const _UrgentNotice({required this.text});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: PalmHills.amberSoft,
        borderRadius: BorderRadius.circular(PalmHills.radiusControl),
        border: Border.all(color: PalmHills.amber.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          const Icon(Icons.phone_in_talk_outlined,
              size: 18, color: PalmHills.amber),
          const SizedBox(width: 10),
          Expanded(
            child: Text(text,
                style: const TextStyle(color: Color(0xFF4A3208), height: 1.4)),
          ),
        ],
      ),
    );
  }
}

class _FiledBanner extends StatelessWidget {
  const _FiledBanner({required this.complaint});

  final Complaint complaint;

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: PalmHills.brandSoft,
        borderRadius: BorderRadius.circular(PalmHills.radiusCard),
        border: Border.all(color: PalmHills.brand.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.check_circle_outline, color: PalmHills.brand),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(s.complaintFiled,
                    style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 4),
                // The reference is the resident's handle on this complaint, so
                // it is selectable rather than merely displayed.
                SelectableText('${s.complaintReference}: ${complaint.complaintId}'),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

// --------------------------------------------------------------------- list

class _ComplaintList extends StatefulWidget {
  const _ComplaintList();

  @override
  State<_ComplaintList> createState() => _ComplaintListState();
}

class _ComplaintListState extends State<_ComplaintList> {
  late Future<List<Complaint>> _future;
  bool _loaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_loaded) return;
    _loaded = true;
    _future = AppScope.of(context).api.complaints();
  }

  /// Block body, not `setState(() => _future = _load())` — see
  /// `policies_screen.dart` for what the arrow form breaks.
  Future<void> _reload() async {
    final future = AppScope.of(context).api.complaints();
    setState(() {
      _future = future;
    });
    try {
      await future;
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return RefreshIndicator(
      onRefresh: _reload,
      child: AsyncBody<List<Complaint>>(
        future: _future,
        onRetry: _reload,
        builder: (context, complaints) {
          if (complaints.isEmpty) {
            return ListView(
              children: [
                const SizedBox(height: 80),
                Center(
                  child: Text(s.noComplaints,
                      style: Theme.of(context).textTheme.bodyMedium),
                ),
              ],
            );
          }
          return ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: complaints.length,
            itemBuilder: (context, i) => _ComplaintCard(
              complaint: complaints[i],
            ),
          );
        },
      ),
    );
  }
}

class _ComplaintCard extends StatelessWidget {
  const _ComplaintCard({required this.complaint});

  final Complaint complaint;

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(complaint.subject,
                      style: Theme.of(context).textTheme.titleMedium),
                ),
                const SizedBox(width: 8),
                _StatusPill(status: complaint.status, closed: complaint.isClosed),
              ],
            ),
            const SizedBox(height: 6),
            SelectableText(
              complaint.complaintId,
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 10),
            Text(complaint.description,
                style: Theme.of(context).textTheme.bodyMedium),
            if (complaint.assignedTeam != null) ...[
              const SizedBox(height: 10),
              Text('${s.complaintRoutedTo}: ${complaint.assignedTeam}',
                  style: Theme.of(context).textTheme.bodySmall),
            ],
            if (complaint.resolution != null &&
                complaint.resolution!.isNotEmpty) ...[
              const SizedBox(height: 10),
              const Divider(),
              const SizedBox(height: 8),
              Text(complaint.resolution!,
                  style: Theme.of(context).textTheme.bodyMedium),
            ],
          ],
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  const _StatusPill({required this.status, required this.closed});

  final String status;
  final bool closed;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
      decoration: BoxDecoration(
        color: closed ? PalmHills.sandDim : PalmHills.brandSoft,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Text(
        status.replaceAll('_', ' '),
        style: TextStyle(
          fontSize: 11.5,
          fontWeight: FontWeight.w700,
          color: closed ? PalmHills.inkSoft : PalmHills.brandDeep,
        ),
      ),
    );
  }
}
