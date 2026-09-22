#define AppName "ИИ пятница 1.0 (бета)"
#define Bundle "..\dist\Пятница"
[Setup]
AppId=FridayAssistantBeta
AppName={#AppName}
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\FridayAI
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=Friday-AI-1.0-beta-Setup
SetupIconFile=..\assets\friday.ico
UninstallDisplayIcon={app}\Пятница.exe
Compression=lzma2/fast
SolidCompression=no
WizardStyle=modern
ShowLanguageDialog=yes
LanguageDetectionMethod=none
DisableWelcomePage=no
CloseApplications=yes
RestartApplications=no
Uninstallable=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "hy"; MessagesFile: "compiler:Languages\Armenian.isl"

[Types]
Name: "cloud"; Description: "{cm:Cloud}"
Name: "full"; Description: "{cm:Full}"
Name: "custom"; Description: "{cm:Custom}"; Flags: iscustom

[Components]
Name: "core"; Description: "{cm:Core}"; Types: cloud full custom; Flags: fixed
Name: "ollama"; Description: "{cm:LocalAI}"; Types: full

[Files]
Source: "{#Bundle}\Пятница.exe"; DestDir: "{app}"; Flags: ignoreversion; Components: core
Source: "{#Bundle}\_internal\*"; DestDir: "{app}\_internal"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core
Source: "{#Bundle}\models\vosk-model-small-ru-0.22\*"; DestDir: "{app}\models\vosk-model-small-ru-0.22"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: core
Source: "{#Bundle}\runtime\ollama\*"; DestDir: "{app}\runtime\ollama"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: ollama
Source: "{#Bundle}\models\ollama\*"; DestDir: "{app}\models\ollama"; Excludes: "*-partial*,*.lock"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: ollama

[Icons]
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\Пятница.exe"; WorkingDir: "{app}"
Name: "{group}\{#AppName}"; Filename: "{app}\Пятница.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\Пятница.exe"; Description: "{cm:Launch}"; Flags: postinstall nowait skipifsilent

[CustomMessages]
ru.Cloud=Программа и голос (облачный ИИ настраивается отдельно)
en.Cloud=Application and voice (configure cloud AI separately)
hy.Cloud=Ծրագիր և ձայն (ամպային ԱԲ-ն կարգավորվում է առանձին)
ru.Full=Программа, голос и локальная Ollama
en.Full=Application, voice and local Ollama
hy.Full=Ծրագիր, ձայն և տեղային Ollama
ru.Custom=Выбор компонентов
en.Custom=Custom components
hy.Custom=Բաղադրիչների ընտրություն
ru.Core=Пятница, библиотеки и распознавание речи Vosk
en.Core=Friday, libraries and Vosk speech recognition
hy.Core=Ուրբաթ, գրադարաններ և Vosk խոսքի ճանաչում
ru.LocalAI=Ollama и локальная модель Qwen (около 3 ГБ)
en.LocalAI=Ollama and local Qwen model (about 3 GB)
hy.LocalAI=Ollama և տեղային Qwen մոդել (մոտ 3 ԳԲ)
ru.Launch=Запустить Пятницу
en.Launch=Launch Friday
hy.Launch=Գործարկել Ուրբաթը
ru.Terms=Конфиденциальность и условия
en.Terms=Privacy and terms
hy.Terms=Գաղտնիություն և պայմաններ
ru.ReadTerms=Прочитайте условия перед установкой
en.ReadTerms=Read the terms before installing
hy.ReadTerms=Տեղադրումից առաջ կարդացեք պայմանները
ru.Accept=Я прочитал(а) и принимаю условия и политику конфиденциальности
en.Accept=I have read and accept the terms and privacy policy
hy.Accept=Կարդացել և ընդունում եմ պայմաններն ու գաղտնիության քաղաքականությունը
ru.Body=ИИ пятница 1.0 (бета). Возможны ошибки: проверяйте ответы ИИ и результаты действий.%n%nИстория, настройки и снимки сохраняются локально. Ключи API защищаются Windows. При использовании облачного ИИ запрос и контекст отправляются выбранному провайдеру. Поиск отправляет запрос поисковику. OCR экрана может включать личные данные в контекст. Google-распознавание отправляет запись голоса; Vosk работает локально.%n%nОблачные сервисы требуют вашего ключа, подключения и соблюдения условий провайдера; возможны лимиты и оплата. Приложение может изменять файлы и настройки по вашим командам. Проверяйте важные действия. Программа не обещает безошибочную работу.%n%nУстановка не включает чужие ключи и историю. Ollama выбирается отдельно. Удаление программы сохраняет пользовательские данные и ключи. Сторонние компоненты сохраняют свои лицензии.%n%nКонтакт проекта: github.com/happyfox102/---------------
en.Body=Friday AI 1.0 (beta). Errors are possible: review AI responses and action results.%n%nHistory, settings and screenshots are stored locally. Windows protects API keys. Cloud AI receives your request and conversation context. Web search sends queries to search engines. Screen OCR can include personal information in context. Google speech recognition sends audio; Vosk works locally.%n%nCloud services require your own key, connectivity and compliance with provider terms; quotas and charges may apply. The application can modify files and settings when instructed. Review important actions. Error-free operation is not promised.%n%nThe installer contains no personal keys or history. Ollama is optional. Uninstall preserves user data and keys. Third-party components retain their own licenses.%n%nProject contact: github.com/happyfox102/---------------
hy.Body=Ուրբաթ ԱԲ 1.0 (բետա)։ Հնարավոր են սխալներ. ստուգեք ԱԲ-ի պատասխաններն ու գործողությունների արդյունքները։%n%nՊատմությունը, կարգավորումներն ու էկրանի նկարները պահվում են տեղային։ API բանալիները պաշտպանում է Windows-ը։ Ամպային ԱԲ-ին ուղարկվում են հարցումն ու զրույցի համատեքստը։ Որոնման հարցումն ուղարկվում է որոնման համակարգին։ Էկրանի OCR-ը կարող է անձնական տվյալներ ներառել համատեքստում։ Google խոսքի ճանաչումն ուղարկում է ձայնագրությունը, իսկ Vosk-ը աշխատում է տեղային։%n%nԱմպային ծառայությունները պահանջում են ձեր բանալին և կապը։ Կարող են գործել սահմանաչափեր և վճարներ։ Ծրագիրը ձեր հրամանով կարող է փոխել ֆայլերն ու կարգավորումները։ Ստուգեք կարևոր գործողությունները։ Անսխալ աշխատանք չի երաշխավորվում։%n%nՏեղադրիչը չի պարունակում անձնական բանալիներ կամ պատմություն։ Ollama-ն ընտրովի է։ Ծրագիրը հեռացնելիս օգտվողի տվյալներն ու բանալիները պահպանվում են։ Այլ բաղադրիչները պահպանում են իրենց լիցենզիաները։%n%nՆախագծի կապ՝ github.com/happyfox102/---------------

[Code]
var TermsPage: TWizardPage; Consent: TNewCheckBox;
procedure ConsentChanged(Sender: TObject);
begin
  WizardForm.NextButton.Enabled := Consent.Checked;
end;
procedure InitializeWizard;
var TextBox: TNewMemo;
begin
  TermsPage := CreateCustomPage(wpWelcome, CustomMessage('Terms'), CustomMessage('ReadTerms'));
  TextBox := TNewMemo.Create(TermsPage);
  TextBox.Parent := TermsPage.Surface;
  TextBox.SetBounds(0, 0, TermsPage.SurfaceWidth, TermsPage.SurfaceHeight - ScaleY(55));
  TextBox.ReadOnly := True;
  TextBox.ScrollBars := ssVertical;
  TextBox.Text := CustomMessage('Body');
  Consent := TNewCheckBox.Create(TermsPage);
  Consent.Parent := TermsPage.Surface;
  Consent.SetBounds(0, TermsPage.SurfaceHeight - ScaleY(48), TermsPage.SurfaceWidth, ScaleY(45));
  Consent.Caption := CustomMessage('Accept');
  Consent.Checked := False;
  Consent.OnClick := @ConsentChanged;
end;
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = TermsPage.ID then WizardForm.NextButton.Enabled := Consent.Checked;
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := (CurPageID <> TermsPage.ID) or Consent.Checked;
end;
function InitializeSetup(): Boolean;
begin
  Result := (not WizardSilent) or (ExpandConstant('{param:ACCEPTTERMS|no}') = 'yes');
end;
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    SaveStringToFile(ExpandConstant('{app}\language.txt'), ActiveLanguage, False);
end;
