import 'package:flutter_test/flutter_test.dart';
import 'package:takeley/api/api_client.dart';
import 'package:takeley/api/device_session.dart';
import 'package:takeley/api/push_api.dart';
import 'package:takeley/main.dart';
import 'package:takeley/services/fcm_service.dart';

void main() {
  testWidgets('TAKELEY push scaffold loads', (WidgetTester tester) async {
    final api = ApiClient();
    final fcm = FcmService(session: DeviceSession(api), pushApi: PushApi(api));
    await tester.pumpWidget(TakeleyPushApp(fcm: fcm));
    expect(find.textContaining('TAKELEY'), findsWidgets);
  });
}
