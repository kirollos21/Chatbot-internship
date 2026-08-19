/// The decorative palm-and-hills motif behind the Home hero.
///
/// Painted rather than shipped as an image: it scales to any hero size without
/// a second asset, costs nothing to download, and stays crisp on every density.
/// Everything is drawn in fractions of the given size, so the same painter works
/// on a phone hero and a tablet one.
///
/// It is deliberately low-contrast — a texture behind the greeting, not a
/// picture competing with it. Nothing here is a logo or a wordmark.
library;

import 'package:flutter/material.dart';

import '../core/theme.dart';

class PalmMotifPainter extends CustomPainter {
  const PalmMotifPainter({this.mirror = false});

  /// Flips the composition for right-to-left layouts, so the palm sits on the
  /// same side as the text's trailing edge in Arabic as it does in English.
  final bool mirror;

  @override
  void paint(Canvas canvas, Size size) {
    if (mirror) {
      canvas.save();
      canvas.translate(size.width, 0);
      canvas.scale(-1, 1);
    }

    _paintDunes(canvas, size);
    _paintPalm(canvas, size);

    if (mirror) canvas.restore();
  }

  /// Two overlapping ridges along the bottom — the "hills".
  void _paintDunes(Canvas canvas, Size size) {
    final far = Paint()..color = Colors.white.withValues(alpha: 0.05);
    final near = Paint()..color = Colors.white.withValues(alpha: 0.07);

    canvas.drawPath(
      Path()
        ..moveTo(0, size.height)
        ..lineTo(0, size.height * 0.74)
        ..quadraticBezierTo(
          size.width * 0.34, size.height * 0.52,
          size.width * 0.72, size.height * 0.78,
        )
        ..quadraticBezierTo(
          size.width * 0.88, size.height * 0.92,
          size.width, size.height * 0.80,
        )
        ..lineTo(size.width, size.height)
        ..close(),
      far,
    );

    canvas.drawPath(
      Path()
        ..moveTo(0, size.height)
        ..lineTo(0, size.height * 0.90)
        ..quadraticBezierTo(
          size.width * 0.46, size.height * 0.70,
          size.width, size.height * 0.94,
        )
        ..lineTo(size.width, size.height)
        ..close(),
      near,
    );
  }

  /// A single stylised palm on the trailing side: one curved trunk, fronds
  /// fanned from its crown, and three dates picked out in gold.
  void _paintPalm(Canvas canvas, Size size) {
    final crown = Offset(size.width * 0.80, size.height * 0.30);
    final scale = size.height / 180;

    final trunk = Paint()
      ..color = Colors.white.withValues(alpha: 0.13)
      ..strokeWidth = 4.5 * scale
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    canvas.drawPath(
      Path()
        ..moveTo(crown.dx + 10 * scale, size.height * 0.98)
        ..quadraticBezierTo(
          crown.dx + 2 * scale, size.height * 0.62,
          crown.dx, crown.dy,
        ),
      trunk,
    );

    final frond = Paint()
      ..color = Colors.white.withValues(alpha: 0.16)
      ..strokeWidth = 3.2 * scale
      ..strokeCap = StrokeCap.round
      ..style = PaintingStyle.stroke;

    // Fanned out from the crown: (sweep, drop, length) per frond. Hand-placed
    // rather than generated from an angle — a real palm is not symmetrical, and
    // an even fan reads as a logo instead of a tree.
    const fronds = <(double, double, double)>[
      (-1.00, -0.34, 0.34),
      (-0.72, 0.10, 0.30),
      (-0.30, -0.52, 0.26),
      (0.34, -0.50, 0.26),
      (0.78, -0.26, 0.30),
      (0.96, 0.16, 0.28),
    ];

    for (final (sweep, drop, length) in fronds) {
      final tip = Offset(
        crown.dx + sweep * size.width * length * 0.55,
        crown.dy + drop * size.height * 0.42,
      );
      final control = Offset(
        crown.dx + sweep * size.width * length * 0.24,
        crown.dy + (drop - 0.62) * size.height * 0.30,
      );
      canvas.drawPath(
        Path()
          ..moveTo(crown.dx, crown.dy)
          ..quadraticBezierTo(control.dx, control.dy, tip.dx, tip.dy),
        frond,
      );
    }

    final dates = Paint()..color = const Color(0xFFD9B25E).withValues(alpha: 0.30);
    for (final offset in const [Offset(-6, 8), Offset(5, 11), Offset(-1, 16)]) {
      canvas.drawCircle(
        crown + Offset(offset.dx * scale, offset.dy * scale),
        3.1 * scale,
        dates,
      );
    }
  }

  @override
  bool shouldRepaint(PalmMotifPainter oldDelegate) =>
      oldDelegate.mirror != mirror;
}

/// The Home hero: brand gradient, palm motif, and whatever content is given.
class PalmHero extends StatelessWidget {
  const PalmHero({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final mirror = Directionality.of(context) == TextDirection.rtl;
    return ClipRRect(
      borderRadius: BorderRadius.circular(22),
      child: DecoratedBox(
        decoration: const BoxDecoration(gradient: PalmHills.heroGradient),
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(painter: PalmMotifPainter(mirror: mirror)),
            ),
            Padding(padding: const EdgeInsets.all(22), child: child),
          ],
        ),
      ),
    );
  }
}
