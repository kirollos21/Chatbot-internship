import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api_client.dart';
import '../core/app_state.dart';
import '../core/models.dart';
import '../widgets/common.dart';

/// Report a violation.
///
/// The flow deliberately never tells the reporting resident "this is violation
/// V0XX". The backend does attach a suggestion for staff triage, but a report
/// stays `reported` until a person verifies it, and presenting an AI guess as a
/// finding would turn a report into an accusation.
class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key});

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final _description = TextEditingController();
  final _location = TextEditingController();
  final _formKey = GlobalKey<FormState>();

  Future<List<Category>>? _categories;
  String? _categoryId;
  XFile? _photo;
  bool _busy = false;
  ViolationReport? _submitted;
  String? _uploadWarning;

  /// The category list is language-independent — `label()` picks the language at
  /// render time — so it is fetched once. It cannot be fetched in `initState`;
  /// see [AppScope.of].
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _categories ??= AppScope.of(context).api.categories();
  }

  @override
  void dispose() {
    _description.dispose();
    _location.dispose();
    super.dispose();
  }

  Future<void> _pickPhoto() async {
    try {
      final picked =
          await ImagePicker().pickImage(source: ImageSource.gallery);
      if (picked != null && mounted) setState(() => _photo = picked);
    } catch (_) {
      // Picker is unavailable on some platforms/browsers; the report itself
      // does not depend on it.
      if (mounted) {
        setState(() => _uploadWarning = 'Photo picker unavailable here.');
      }
    }
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false) || _busy) return;
    final state = AppScope.of(context);
    setState(() {
      _busy = true;
      _uploadWarning = null;
    });

    try {
      var report = await state.api.createReport(
        description: _description.text.trim(),
        categoryId: _categoryId,
        locationText: _location.text.trim(),
        compound: state.compound,
        phase: state.phase,
      );

      if (_photo != null) {
        try {
          final bytes = await _photo!.readAsBytes();
          report = await state.api.attachEvidence(
            reportId: report.reportId,
            bytes: bytes,
            filename: _photo!.name,
            contentType: _photo!.mimeType ?? 'image/jpeg',
          );
        } on ApiException catch (e) {
          // The report is already filed; surface the attachment problem
          // without pretending the whole submission failed.
          _uploadWarning = e.message;
        }
      }

      if (!mounted) return;
      setState(() => _submitted = report);
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

    if (_submitted != null) {
      return _Submitted(
        report: _submitted!,
        warning: _uploadWarning,
        onAnother: () => setState(() {
          _submitted = null;
          _description.clear();
          _location.clear();
          _photo = null;
          _categoryId = null;
          _uploadWarning = null;
        }),
      );
    }

    return Form(
      key: _formKey,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(s.reportTitle, style: Theme.of(context).textTheme.titleLarge),
          const SizedBox(height: 16),
          FutureBuilder<List<Category>>(
            future: _categories,
            builder: (context, snapshot) {
              final categories = snapshot.data ?? const <Category>[];
              return DropdownButtonFormField<String>(
                initialValue: _categoryId,
                isExpanded: true,
                decoration: InputDecoration(labelText: s.category),
                items: [
                  for (final category in categories)
                    DropdownMenuItem(
                      value: category.id,
                      child: Text(
                        category.label(state.contentLanguage),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                ],
                onChanged: (v) => setState(() => _categoryId = v),
              );
            },
          ),
          const SizedBox(height: 14),
          TextFormField(
            controller: _description,
            minLines: 3,
            maxLines: 6,
            maxLength: 4000,
            decoration: InputDecoration(labelText: s.description),
            validator: (v) => (v == null || v.trim().length < 5)
                ? s.descriptionRequired
                : null,
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller: _location,
            decoration: InputDecoration(labelText: s.location),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              OutlinedButton.icon(
                onPressed: _busy ? null : _pickPhoto,
                icon: const Icon(Icons.photo_camera_outlined),
                label: Text(s.attachPhoto),
              ),
              const SizedBox(width: 12),
              if (_photo != null)
                Expanded(
                  child: Text(_photo!.name, overflow: TextOverflow.ellipsis),
                ),
            ],
          ),
          if (_uploadWarning != null) ...[
            const SizedBox(height: 8),
            UnavailableNotice(message: _uploadWarning!),
          ],
          const SizedBox(height: 20),
          FilledButton(
            onPressed: _busy ? null : _submit,
            child: _busy
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(s.submit),
          ),
          const SizedBox(height: 16),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(14),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Icon(Icons.info_outline, size: 18),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Text(
                      s.reportDisclaimer,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Submitted extends StatelessWidget {
  const _Submitted({
    required this.report,
    required this.onAnother,
    this.warning,
  });

  final ViolationReport report;
  final VoidCallback onAnother;
  final String? warning;

  @override
  Widget build(BuildContext context) {
    final s = AppScope.of(context).strings;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.check_circle_outline,
                size: 48, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 12),
            Text(s.reportSubmitted,
                style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 6),
            SelectableText(report.reportId),
            if (warning != null) ...[
              const SizedBox(height: 12),
              UnavailableNotice(message: warning!),
            ],
            const SizedBox(height: 16),
            Text(
              // The backend's own disclaimer, shown verbatim.
              report.disclaimer.isEmpty ? s.reportDisclaimer : report.disclaimer,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 20),
            OutlinedButton(onPressed: onAnother, child: Text(s.reportTitle)),
          ],
        ),
      ),
    );
  }
}
