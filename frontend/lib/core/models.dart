/// Response models mirroring the backend schemas.
///
/// Note what these deliberately do *not* do: no model computes, formats or
/// infers a penalty, and none substitutes a fallback when a contact or facility
/// field is null. `availability` and the accompanying `message` come from the
/// backend, which is the only component that knows whether a value is real.
library;

String _s(dynamic v) => v == null ? '' : '$v';

class Category {
  Category({required this.id, required this.en, required this.ar});

  factory Category.fromJson(Map<String, dynamic> j) => Category(
        id: _s(j['category_id']),
        en: _s(j['category_en']),
        ar: _s(j['category_ar']),
      );

  final String id;
  final String en;
  final String ar;

  String label(String language) => language == 'ar' ? ar : en;
}

class SourceRef {
  SourceRef({
    required this.id,
    required this.kind,
    required this.categoryId,
    required this.label,
  });

  factory SourceRef.fromJson(Map<String, dynamic> j) => SourceRef(
        id: _s(j['id']),
        kind: _s(j['kind']),
        categoryId: _s(j['category_id']),
        label: _s(j['label']),
      );

  final String id;
  final String kind;
  final String categoryId;
  final String label;
}

/// A Palm Hills project a resident can select as their location.
///
/// [compound] is what goes back to the API and is deliberately not always the
/// same as [id]: several North Coast projects share one scoping token, because
/// that is the only scope the shipped regulations distinguish. The backend owns
/// that decision - see `app/services/projects.py`.
class Project {
  const Project({
    required this.id,
    required this.nameEn,
    required this.nameAr,
    required this.region,
    required this.regionEn,
    required this.regionAr,
    required this.compound,
  });

  factory Project.fromJson(Map<String, dynamic> j) => Project(
        id: _s(j['id']),
        nameEn: _s(j['name_en']),
        nameAr: _s(j['name_ar']),
        region: _s(j['region']),
        regionEn: _s(j['region_en']),
        regionAr: _s(j['region_ar']),
        compound: _s(j['compound']),
      );

  final String id;
  final String nameEn;
  final String nameAr;
  final String region;
  final String regionEn;
  final String regionAr;
  final String compound;

  String name(String language) => language == 'ar' ? nameAr : nameEn;
  String regionLabel(String language) => language == 'ar' ? regionAr : regionEn;
}

class ChatAnswer {
  ChatAnswer({
    required this.answer,
    required this.language,
    required this.detectedLanguage,
    required this.intent,
    required this.confidenceBand,
    required this.needsClarification,
    required this.escalated,
    required this.sources,
    this.ticketId,
    this.policyVersion,
  });

  factory ChatAnswer.fromJson(Map<String, dynamic> j) => ChatAnswer(
        answer: _s(j['answer']),
        language: _s(j['language']),
        detectedLanguage: _s(j['detected_language']),
        intent: _s(j['intent']),
        confidenceBand: _s(j['confidence_band']),
        needsClarification: j['needs_clarification'] == true,
        escalated: j['escalated'] == true,
        ticketId: j['ticket_id'] as String?,
        policyVersion: j['policy_version'] as String?,
        sources: ((j['sources'] as List?) ?? const [])
            .map((e) => SourceRef.fromJson(e as Map<String, dynamic>))
            .toList(),
      );

  final String answer;
  final String language;
  final String detectedLanguage;
  final String intent;
  final String confidenceBand;
  final bool needsClarification;
  final bool escalated;
  final String? ticketId;
  final String? policyVersion;
  final List<SourceRef> sources;

  bool get isLowConfidence => confidenceBand == 'low';
}

class Policy {
  Policy({
    required this.id,
    required this.categoryId,
    required this.en,
    required this.ar,
    required this.srcEn,
    required this.srcAr,
  });

  factory Policy.fromJson(Map<String, dynamic> j) => Policy(
        id: _s(j['id']),
        categoryId: _s(j['category_id']),
        en: _s(j['rule_en']),
        ar: _s(j['rule_ar']),
        srcEn: _s(j['src_en']),
        srcAr: _s(j['src_ar']),
      );

  final String id;
  final String categoryId;
  final String en;
  final String ar;
  final String srcEn;
  final String srcAr;

  String text(String language) => language == 'ar' ? ar : en;

  /// True when the text shown was translated during data preparation rather
  /// than taken from the source document in that language.
  bool isDerived(String language) =>
      language == 'ar' ? srcAr == 'derived' : srcEn == 'derived';
}

class Violation {
  Violation({
    required this.id,
    required this.categoryId,
    required this.en,
    required this.ar,
    required this.penaltyEgp,
    required this.actionEn,
    required this.actionAr,
    required this.relatedPolicyIds,
  });

  factory Violation.fromJson(Map<String, dynamic> j) => Violation(
        id: _s(j['id']),
        categoryId: _s(j['category_id']),
        en: _s(j['violation_en']),
        ar: _s(j['violation_ar']),
        // Kept as the exact integer the backend sent. Never rounded, never
        // reformatted into another currency or unit.
        penaltyEgp: (j['penalty_egp'] as num).toInt(),
        actionEn: _s(j['action_en']),
        actionAr: _s(j['action_ar']),
        relatedPolicyIds:
            ((j['related_policy_ids'] as List?) ?? const []).map(_s).toList(),
      );

  final String id;
  final String categoryId;
  final String en;
  final String ar;
  final int penaltyEgp;
  final String actionEn;
  final String actionAr;
  final List<String> relatedPolicyIds;

  String text(String language) => language == 'ar' ? ar : en;
  String action(String language) => language == 'ar' ? actionAr : actionEn;

  /// Thousands separators only — the value itself is untouched.
  String get penaltyFormatted {
    final digits = penaltyEgp.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i > 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }
}

class Facility {
  Facility({
    required this.id,
    required this.nameEn,
    required this.nameAr,
    required this.facilityType,
    required this.restrictions,
    required this.availability,
    this.compound,
    this.phase,
    this.locationNote,
    this.hours,
    this.hoursSource,
    this.message,
    this.contactId,
  });

  factory Facility.fromJson(Map<String, dynamic> j) => Facility(
        id: _s(j['id']),
        nameEn: _s(j['name_en']),
        nameAr: _s(j['name_ar']),
        facilityType: _s(j['facility_type']),
        compound: j['compound'] as String?,
        phase: j['phase'] as String?,
        locationNote: j['location_note'] as String?,
        hours: j['hours'] as String?,
        hoursSource: j['hours_source'] as String?,
        contactId: j['contact_id'] as String?,
        availability: _s(j['availability']),
        message: j['message'] as String?,
        restrictions:
            ((j['restrictions'] as List?) ?? const []).map(_s).toList(),
      );

  final String id;
  final String nameEn;
  final String nameAr;
  final String facilityType;
  final String? compound;
  final String? phase;
  final String? locationNote;
  final String? hours;
  final String? hoursSource;
  final String? contactId;
  final String availability;
  final String? message;
  final List<String> restrictions;

  String name(String language) => language == 'ar' ? nameAr : nameEn;
  bool get isConfigured => availability == 'configured';
  bool get hasHours => hours != null && hours!.isNotEmpty;
}

class Contact {
  Contact({
    required this.id,
    required this.nameEn,
    required this.nameAr,
    required this.role,
    required this.availability,
    this.phone,
    this.email,
    this.hours,
    this.message,
    this.source,
  });

  /// A real number, confirmed by Community Management.
  static const configured = 'configured';

  /// A number Palm Hills lists publicly that Community Management has not
  /// confirmed. Dialable, but shown with its caveat — see
  /// `app/services/directory.py` for why this state exists.
  static const unverified = 'unverified';

  factory Contact.fromJson(Map<String, dynamic> j) => Contact(
        id: _s(j['id']),
        nameEn: _s(j['name_en']),
        nameAr: _s(j['name_ar']),
        role: _s(j['role']),
        phone: j['phone'] as String?,
        email: j['email'] as String?,
        hours: j['hours'] as String?,
        availability: _s(j['availability']),
        message: j['message'] as String?,
        source: j['source'] as String?,
      );

  final String id;
  final String nameEn;
  final String nameAr;
  final String role;
  final String? phone;
  final String? email;
  final String? hours;
  final String availability;
  final String? message;

  /// Where an [unverified] number came from. Null for dataset contacts.
  final String? source;

  String name(String language) => language == 'ar' ? nameAr : nameEn;

  /// The backend nulls the phone unless it has one, so a non-empty value here
  /// is always a real number — but see [isUnverified] before presenting it as
  /// authoritative.
  bool get hasPhone => phone != null && phone!.isNotEmpty;

  bool get isUnverified => availability == unverified;
}

/// A category the complaint form offers. Served by the backend so the teams
/// complaints route to stay a backend concern.
class ComplaintCategory {
  const ComplaintCategory({
    required this.id,
    required this.labelEn,
    required this.labelAr,
    required this.team,
    required this.urgent,
  });

  factory ComplaintCategory.fromJson(Map<String, dynamic> j) => ComplaintCategory(
        id: _s(j['id']),
        labelEn: _s(j['label_en']),
        labelAr: _s(j['label_ar']),
        team: _s(j['team']),
        urgent: j['urgent'] == true,
      );

  final String id;
  final String labelEn;
  final String labelAr;
  final String team;

  /// A form is the wrong channel for this — the resident should call.
  final bool urgent;

  String label(String language) => language == 'ar' ? labelAr : labelEn;
}

class Complaint {
  Complaint({
    required this.complaintId,
    required this.category,
    required this.subject,
    required this.description,
    required this.status,
    required this.createdAt,
    this.assignedTeam,
    this.resolution,
    this.locationText,
    this.resolvedAt,
  });

  factory Complaint.fromJson(Map<String, dynamic> j) => Complaint(
        complaintId: _s(j['complaint_id']),
        category: _s(j['category']),
        subject: _s(j['subject']),
        description: _s(j['description']),
        status: _s(j['status']),
        assignedTeam: j['assigned_team'] as String?,
        resolution: j['resolution'] as String?,
        locationText: j['location_text'] as String?,
        createdAt: DateTime.tryParse(_s(j['created_at'])) ?? DateTime.now(),
        resolvedAt: DateTime.tryParse(_s(j['resolved_at'])),
      );

  final String complaintId;
  final String category;
  final String subject;
  final String description;
  final String status;
  final String? assignedTeam;
  final String? resolution;
  final String? locationText;
  final DateTime createdAt;
  final DateTime? resolvedAt;

  bool get isClosed => status == 'resolved' || status == 'closed';
}

class Ticket {
  Ticket({
    required this.ticketId,
    required this.status,
    required this.reason,
    required this.createdAt,
    this.assignedTeam,
    this.resolution,
    this.resolvedAt,
  });

  factory Ticket.fromJson(Map<String, dynamic> j) => Ticket(
        ticketId: _s(j['ticket_id']),
        status: _s(j['status']),
        reason: _s(j['reason']),
        assignedTeam: j['assigned_team'] as String?,
        resolution: j['resolution'] as String?,
        createdAt: DateTime.tryParse(_s(j['created_at'])),
        resolvedAt: DateTime.tryParse(_s(j['resolved_at'])),
      );

  final String ticketId;
  final String status;
  final String reason;
  final String? assignedTeam;
  final String? resolution;
  final DateTime? createdAt;
  final DateTime? resolvedAt;
}

class ViolationReport {
  ViolationReport({
    required this.reportId,
    required this.status,
    required this.description,
    required this.attachments,
    required this.disclaimer,
    this.categoryId,
    this.locationText,
    this.suggestedViolationId,
    this.createdAt,
  });

  factory ViolationReport.fromJson(Map<String, dynamic> j) => ViolationReport(
        reportId: _s(j['report_id']),
        status: _s(j['status']),
        description: _s(j['description']),
        categoryId: j['category_id'] as String?,
        locationText: j['location_text'] as String?,
        suggestedViolationId: j['suggested_violation_id'] as String?,
        disclaimer: _s(j['suggested_disclaimer']),
        createdAt: DateTime.tryParse(_s(j['created_at'])),
        attachments: ((j['attachments'] as List?) ?? const []).length,
      );

  final String reportId;
  final String status;
  final String description;
  final String? categoryId;
  final String? locationText;

  /// A staff triage hint only. The UI must not present this to the reporting
  /// resident as "you committed/witnessed violation X" — nothing is a verified
  /// violation until a person confirms it.
  final String? suggestedViolationId;
  final String disclaimer;
  final DateTime? createdAt;
  final int attachments;
}
