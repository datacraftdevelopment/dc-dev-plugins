//
//  ADTHelper.mm — ADT Helper plug-in for Claris FileMaker Pro
//
//  Purpose-built for agentic development: gives a coding agent eyes and hands
//  inside FileMaker Pro's own process — window/web-viewer snapshots (no macOS
//  Screen Recording permission), state probes, script starting, FileMaker XML
//  clipboard access, and a drop-folder command channel driven from the
//  plug-in idle loop.
//
//  Functions registered (plugin ID 'ADTh'):
//    ADTH_Version                                    -> version string
//    ADTH_WindowList                                 -> JSON array of open windows
//    ADTH_WindowSnapshot( path { ; windowTitle } )   -> writes PNG, "OK …" | "ERROR: …"
//    ADTH_Snapshot( path ; optionsJSON )             -> snapshot with region/scale options
//    ADTH_WebViewerSnapshot( path { ; windowTitle ; index } ) -> WKWebView pixels
//    ADTH_State                                      -> JSON of Get() probes
//    ADTH_RunScript( fileName ; scriptName { ; param ; control } ) -> queue a script
//    ADTH_ClipboardFormats                           -> JSON of pasteboard flavors
//    ADTH_ClipboardGetXML( { code } )                -> FileMaker XML off the clipboard
//    ADTH_ClipboardSetXML( xml { ; code } )          -> FileMaker XML onto the clipboard
//    ADTH_ChannelStart( folder )                     -> begin idle-loop command channel
//    ADTH_ChannelStop                                -> end it
//    ADTH_ChannelStatus                              -> JSON status
//
//  Built against the Claris FileMaker Plug-In SDK (FMWrapper). The SDK's
//  license permits compiling plug-ins for use with Claris products.
//

#import <Cocoa/Cocoa.h>
#import <WebKit/WebKit.h>
#import <CoreServices/CoreServices.h>

#include "FMWrapper/FMXTypes.h"
#include "FMWrapper/FMXText.h"
#include "FMWrapper/FMXFixPt.h"
#include "FMWrapper/FMXData.h"
#include "FMWrapper/FMXCalcEngine.h"
#include "FMWrapper/FMXExtern.h"

#include <string>
#include <vector>

static const char* kADTh( "ADTh" );
static const char* kVersionString( "ADT Helper 0.4.1" );

enum {
    kADTH_VersionID            = 100,
    kADTH_WindowListID         = 200,
    kADTH_WindowSnapshotID     = 300,
    kADTH_SnapshotID           = 310,
    kADTH_WebViewerSnapshotID  = 320,
    kADTH_WebViewerListID      = 330,
    kADTH_StateID              = 400,
    kADTH_RunScriptID          = 500,
    kADTH_ClipboardFormatsID   = 600,
    kADTH_ClipboardGetXMLID    = 610,
    kADTH_ClipboardSetXMLID    = 620,
    kADTH_ChannelStartID       = 700,
    kADTH_ChannelStopID        = 710,
    kADTH_ChannelStatusID      = 720,
};

// ---- fmx <-> Foundation helpers ---------------------------------------------------------

static NSString* NSStringFromFMXText( const fmx::Text& txt )
{
    const fmx::uint32 size = txt.GetSize();
    if (size == 0) return @"";
    std::vector<fmx::unichar16> buf( size );
    txt.GetUnicode( buf.data(), 0, size );
    return [NSString stringWithCharacters:reinterpret_cast<const unichar*>(buf.data()) length:size];
}

static void AssignFMXText( fmx::Text& txt, NSString* str )
{
    txt.Assign( str.UTF8String ? str.UTF8String : "", fmx::Text::kEncoding_UTF8 );
}

static void SetTextResult( fmx::Data& results, NSString* str )
{
    fmx::TextUniquePtr out;
    AssignFMXText( *out, str );
    results.SetAsText( *out, results.GetLocale() );
}

static void RunOnMain( void (^block)(void) )
{
    if ([NSThread isMainThread]) { block(); }
    else { dispatch_sync( dispatch_get_main_queue(), block ); }
}

static NSString* JSONString( id obj )
{
    if (obj == nil) return @"null";
    NSData* d = [NSJSONSerialization dataWithJSONObject:obj options:NSJSONWritingPrettyPrinted error:nil];
    if (!d) return @"null";
    return [[NSString alloc] initWithData:d encoding:NSUTF8StringEncoding];
}

// Evaluate a FileMaker calc expression through an environment; nil on error.
static NSString* EvalExpr( const fmx::ExprEnv& env, NSString* expr )
{
    fmx::TextUniquePtr t;
    AssignFMXText( *t, [NSString stringWithFormat:@"GetAsText ( %@ )", expr] );
    fmx::DataUniquePtr d;
    if (env.Evaluate( *t, *d ) != 0) return nil;
    return NSStringFromFMXText( d->GetAsText() );
}

// ---- window + snapshot core -------------------------------------------------------------

static NSWindow* FindWindow( NSString* title )
{
    for (NSWindow* w in [NSApp orderedWindows])
    {
        if (!w.isVisible || w.isMiniaturized) continue;
        if (title.length > 0)
        {
            if ([w.title localizedCaseInsensitiveContainsString:title]) return w;
        }
        else if (w.title.length > 0) return w;
    }
    return nil;
}

// Capture a window's content view. region (in view points, top-left origin) may be
// NSZeroRect for the whole view; scale 0 keeps the backing scale, 1 forces 1x output.
static NSString* SnapshotWindowCore( NSWindow* target, NSRect region, CGFloat scale, NSString* path )
{
    NSView* view = target.contentView;
    NSRect bounds = view.bounds;
    if (bounds.size.width < 1 || bounds.size.height < 1)
        return @"ERROR: window content view has zero size";

    NSRect capture = bounds;
    if (!NSIsEmptyRect( region ))
    {
        // convert from top-left-origin points to the view's coordinate space
        NSRect r = region;
        if (!view.isFlipped)
            r.origin.y = bounds.size.height - region.origin.y - region.size.height;
        capture = NSIntersectionRect( r, bounds );
        if (NSIsEmptyRect( capture ))
            return @"ERROR: region lies outside the window content";
    }

    NSBitmapImageRep* rep = [view bitmapImageRepForCachingDisplayInRect:capture];
    if (rep == nil) return @"ERROR: could not allocate bitmap";
    [view cacheDisplayInRect:capture toBitmapImageRep:rep];

    // optional resample to an exact scale (points * scale)
    if (scale > 0.01)
    {
        const NSInteger outW = (NSInteger)llround( capture.size.width  * scale );
        const NSInteger outH = (NSInteger)llround( capture.size.height * scale );
        if (outW != rep.pixelsWide || outH != rep.pixelsHigh)
        {
            NSBitmapImageRep* scaled = [[NSBitmapImageRep alloc]
                initWithBitmapDataPlanes:NULL pixelsWide:outW pixelsHigh:outH
                bitsPerSample:8 samplesPerPixel:4 hasAlpha:YES isPlanar:NO
                colorSpaceName:NSCalibratedRGBColorSpace bytesPerRow:0 bitsPerPixel:0];
            if (scaled)
            {
                NSGraphicsContext* ctx = [NSGraphicsContext graphicsContextWithBitmapImageRep:scaled];
                [NSGraphicsContext saveGraphicsState];
                [NSGraphicsContext setCurrentContext:ctx];
                ctx.imageInterpolation = NSImageInterpolationHigh;
                [rep drawInRect:NSMakeRect( 0, 0, outW, outH )];
                [NSGraphicsContext restoreGraphicsState];
                rep = scaled;
            }
        }
    }

    NSData* png = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
    if (png == nil) return @"ERROR: PNG encoding failed";

    [[NSFileManager defaultManager] createDirectoryAtPath:[path stringByDeletingLastPathComponent]
                              withIntermediateDirectories:YES attributes:nil error:nil];
    NSError* werr = nil;
    if (![png writeToFile:path options:NSDataWritingAtomic error:&werr])
        return [NSString stringWithFormat:@"ERROR: write failed: %@", werr.localizedDescription ?: @"unknown"];

    return [NSString stringWithFormat:@"OK: %@ (%dx%d, window \"%@\")",
            path, (int)rep.pixelsWide, (int)rep.pixelsHigh, target.title];
}

static NSString* SnapshotByTitle( NSString* title, NSRect region, CGFloat scale, NSString* path )
{
    __block NSString* outcome = @"ERROR: unknown";
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil)
        {
            outcome = [NSString stringWithFormat:@"ERROR: no visible window%@",
                       title.length ? [NSString stringWithFormat:@" matching \"%@\"", title] : @""];
            return;
        }
        outcome = SnapshotWindowCore( target, region, scale, path );
    } );
    return outcome;
}

// ---- web viewer capture -----------------------------------------------------------------

static void CollectWebViews( NSView* v, NSMutableArray<WKWebView*>* into )
{
    if ([v isKindOfClass:[WKWebView class]]) [into addObject:(WKWebView*)v];
    for (NSView* sub in v.subviews) CollectWebViews( sub, into );
}

static NSString* WebViewerSnapshot( NSString* title, NSInteger index, NSString* path )
{
    __block NSString* outcome = @"ERROR: unknown";
    __block WKWebView* web = nil;
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil) { outcome = @"ERROR: no matching visible window"; return; }
        NSMutableArray<WKWebView*>* views = [NSMutableArray array];
        CollectWebViews( target.contentView, views );
        if ((NSUInteger)index >= views.count)
        {
            outcome = [NSString stringWithFormat:@"ERROR: window has %lu web viewer(s), index %ld out of range",
                       (unsigned long)views.count, (long)index];
            return;
        }
        web = views[(NSUInteger)index];
        outcome = nil; // signals "proceed"
    } );
    if (outcome != nil) return outcome;

    // WKWebView snapshots are async; pump the run loop (we are on FileMaker's
    // main thread when called from a calc) until completion or timeout.
    __block NSString* result = nil;
    RunOnMain( ^{
        WKSnapshotConfiguration* cfg = [WKSnapshotConfiguration new];
        [web takeSnapshotWithConfiguration:cfg completionHandler:^(NSImage* img, NSError* err) {
            if (img == nil)
            {
                result = [NSString stringWithFormat:@"ERROR: snapshot failed: %@",
                          err.localizedDescription ?: @"unknown"];
                return;
            }
            NSBitmapImageRep* rep = [[NSBitmapImageRep alloc] initWithData:img.TIFFRepresentation];
            NSData* png = [rep representationUsingType:NSBitmapImageFileTypePNG properties:@{}];
            if (png == nil) { result = @"ERROR: PNG encoding failed"; return; }
            [[NSFileManager defaultManager] createDirectoryAtPath:[path stringByDeletingLastPathComponent]
                                      withIntermediateDirectories:YES attributes:nil error:nil];
            NSError* werr = nil;
            if (![png writeToFile:path options:NSDataWritingAtomic error:&werr])
            {
                result = [NSString stringWithFormat:@"ERROR: write failed: %@",
                          werr.localizedDescription ?: @"unknown"];
                return;
            }
            result = [NSString stringWithFormat:@"OK: %@ (%dx%d, web viewer)",
                      path, (int)rep.pixelsWide, (int)rep.pixelsHigh];
        }];
    } );

    NSDate* deadline = [NSDate dateWithTimeIntervalSinceNow:5.0];
    while (result == nil && [deadline timeIntervalSinceNow] > 0)
        [[NSRunLoop currentRunLoop] runMode:NSDefaultRunLoopMode
                                 beforeDate:[NSDate dateWithTimeIntervalSinceNow:0.05]];
    return result ?: @"ERROR: snapshot timed out (5s)";
}

// Enumerate the web viewers in a window so an agent can pick a snapshot index.
static NSString* WebViewerListJSON( NSString* title )
{
    __block NSString* json = @"[]";
    __block NSString* err = nil;
    RunOnMain( ^{
        NSWindow* target = FindWindow( title );
        if (target == nil) { err = @"ERROR: no matching visible window"; return; }
        NSMutableArray* arr = [NSMutableArray array];
        NSMutableArray<WKWebView*>* views = [NSMutableArray array];
        CollectWebViews( target.contentView, views );
        [views enumerateObjectsUsingBlock:^(WKWebView* w, NSUInteger i, BOOL*) {
            [arr addObject:@{
                @"index":   @(i),
                @"url":     w.URL.absoluteString ?: @"",
                @"title":   w.title ?: @"",
                @"loading": @(w.isLoading),
                @"width":   @((int)w.frame.size.width),
                @"height":  @((int)w.frame.size.height),
            }];
        }];
        json = JSONString( arr );
    } );
    return err ?: json;
}

// ---- clipboard: FileMaker XML flavors ---------------------------------------------------

// FileMaker's Mac clipboard flavors are classic four-char OSTypes. The reliable,
// deterministic pasteboard type string for one is the legacy bridge form
// "CorePasteboardFlavorType 0x<hex>" — reading and writing it round-trips with
// the dyn.* UTI FileMaker itself advertises (verified against FM 26; the
// deprecated UTTypeCreatePreferredIdentifierForTag derivation returns a short
// dyn form FileMaker does NOT use).
static NSString* FlavorForFMCode( NSString* code )
{
    if (code.length != 4) return nil;
    const char* c = code.UTF8String;
    return [NSString stringWithFormat:@"CorePasteboardFlavorType 0x%02X%02X%02X%02X",
            c[0], c[1], c[2], c[3]];
}

// Decode "CorePasteboardFlavorType 0x584D5353" back to "XMSS" (nil if not that shape).
static NSString* FMCodeFromFlavorType( NSString* type )
{
    NSString* prefix = @"CorePasteboardFlavorType 0x";
    if (![type hasPrefix:prefix] || type.length != prefix.length + 8) return nil;
    unsigned value = 0;
    if (![[NSScanner scannerWithString:[type substringFromIndex:prefix.length]] scanHexInt:&value]) return nil;
    char c[5] = { (char)(value >> 24), (char)(value >> 16), (char)(value >> 8), (char)value, 0 };
    for (int i = 0; i < 4; i++) if (c[i] < 0x20 || c[i] > 0x7E) return nil;
    return @(c);
}

static NSDictionary<NSString*, NSString*>* FMClipboardCodes( void )
{
    // code -> what it carries
    return @{
        @"XMTB": @"tables",
        @"XMFD": @"fields",
        @"XMSC": @"scripts",
        @"XMSS": @"script steps",
        @"XML2": @"layout objects",
        @"XMLO": @"layout objects (legacy)",
        @"XMVL": @"value lists",
        @"XMFN": @"custom functions",
    };
}

static NSString* XMLFromClipboardData( NSData* data )
{
    if (data.length == 0) return nil;
    const uint8_t* bytes = (const uint8_t*)data.bytes;
    // plain UTF-8 XML
    if (bytes[0] == '<')
        return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    // UTF-16 BOM
    if (data.length >= 2 && ((bytes[0] == 0xFF && bytes[1] == 0xFE) || (bytes[0] == 0xFE && bytes[1] == 0xFF)))
        return [[NSString alloc] initWithData:data encoding:NSUTF16StringEncoding];
    // 4-byte length prefix (Windows-style payloads travel sometimes)
    if (data.length > 4 && bytes[4] == '<')
        return [[NSString alloc] initWithData:[data subdataWithRange:NSMakeRange( 4, data.length - 4 )]
                                     encoding:NSUTF8StringEncoding];
    return [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
}

// Guess the FM flavor for a snippet by its first child element. Order matters:
// scripts contain steps, layouts contain fields.
static NSString* SniffFMCode( NSString* xml )
{
    NSArray* probes = @[
        @[@"<Layout",         @"XML2"],
        @[@"<Script",         @"XMSC"],
        @[@"<Step",           @"XMSS"],
        @[@"<ValueList",      @"XMVL"],
        @[@"<CustomFunction", @"XMFN"],
        @[@"<BaseTable",      @"XMTB"],
        @[@"<Field",          @"XMFD"],
    ];
    for (NSArray* p in probes)
        if ([xml containsString:p[0]]) return p[1];
    return nil;
}

static NSString* ClipboardFormatsJSON( void )
{
    __block NSString* json = @"[]";
    RunOnMain( ^{
        NSMutableArray* arr = [NSMutableArray array];
        NSDictionary* codes = FMClipboardCodes();
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        for (NSPasteboardType t in pb.types)
        {
            NSMutableDictionary* entry = [@{ @"uti": t } mutableCopy];
            NSString* code = FMCodeFromFlavorType( t );
            if (code)
            {
                entry[@"fmCode"] = code;
                entry[@"carries"] = codes[code] ?: @"unknown four-char flavor";
            }
            [arr addObject:entry];
        }
        json = JSONString( arr );
    } );
    return json;
}

static NSString* ClipboardGetXML( NSString* code )
{
    __block NSString* out = @"ERROR: no FileMaker XML on the clipboard";
    RunOnMain( ^{
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        if (code.length)
        {
            NSString* flavor = FlavorForFMCode( code );
            NSData* d = flavor ? [pb dataForType:flavor] : nil;
            NSString* xml = d.length ? XMLFromClipboardData( d ) : nil;
            out = xml.length ? xml
                : [NSString stringWithFormat:@"ERROR: no clipboard data for FileMaker flavor %@", code];
            return;
        }
        // no code given: any four-char CorePasteboardFlavorType on the board counts,
        // known to the table or not
        for (NSPasteboardType t in pb.types)
        {
            if (FMCodeFromFlavorType( t ) == nil) continue;
            NSData* d = [pb dataForType:t];
            if (d.length)
            {
                NSString* xml = XMLFromClipboardData( d );
                if (xml.length) { out = xml; return; }
            }
        }
    } );
    return out;
}

static NSString* ClipboardSetXML( NSString* xml, NSString* code )
{
    NSString* useCode = code.length ? code : SniffFMCode( xml );
    if (useCode.length == 0)
        return @"ERROR: could not infer the FileMaker flavor; pass a code (XMSS, XMSC, XML2, XMTB, XMFD, XMVL, XMFN)";
    NSString* flavor = FlavorForFMCode( useCode );
    if (flavor == nil) return @"ERROR: flavor code must be 4 characters (e.g. XMSS)";

    __block NSString* out;
    RunOnMain( ^{
        NSPasteboard* pb = [NSPasteboard generalPasteboard];
        [pb clearContents];
        [pb declareTypes:@[flavor] owner:nil];
        BOOL ok = [pb setData:[xml dataUsingEncoding:NSUTF8StringEncoding] forType:flavor];
        out = ok ? [NSString stringWithFormat:@"OK: %lu bytes on clipboard as %@ (%@)",
                    (unsigned long)[xml lengthOfBytesUsingEncoding:NSUTF8StringEncoding],
                    useCode, FMClipboardCodes()[useCode] ?: @"?"]
                 : @"ERROR: pasteboard write failed";
    } );
    return out;
}

// ---- state probe ------------------------------------------------------------------------

// which FileMaker copy hosts this plug-in (defined with the auto-arm code below)
static NSString* HostAppName( void );

// command-channel state, declared here so the state probe can report it
static NSString* gChannelFolder = nil;
static BOOL      gChannelActive = NO;
static NSUInteger gChannelProcessed = 0;
static NSString* gChannelLastError = nil;

// auto-arm (0.4.0): idle reads ~/.adt-helper/config.json and arms the channel
// for an allowlisted frontmost file with no script run. The config file is the
// opt-in. An explicit ADTH_ChannelStop suppresses auto-arm until the config
// file's mtime changes (re-consent) or FileMaker restarts.
static NSTimeInterval gAutoArmLastCheck = 0;           // throttle: stat config at most every few sec
static NSTimeInterval gAutoArmSuppressMtime = 0;       // config mtime at which a manual stop was issued
static BOOL      gChannelAutoArmed = NO;               // reported in state/status

static NSString* StateJSON( const fmx::ExprEnv& env )
{
    NSDictionary* probes = @{
        @"file":            @"Get ( FileName )",
        @"layout":          @"Get ( LayoutName )",
        @"layoutNumber":    @"Get ( LayoutNumber )",
        @"table":           @"Get ( LayoutTableName )",
        @"window":          @"Get ( WindowName )",
        @"windowMode":      @"Get ( WindowMode )",
        @"foundCount":      @"Get ( FoundCount )",
        @"totalRecords":    @"Get ( TotalRecordCount )",
        @"recordsOpen":     @"Get ( RecordOpenCount )",
        @"lastError":       @"Get ( LastError )",
        @"scriptRunning":   @"Get ( ScriptName )",
        @"account":         @"Get ( AccountName )",
        @"appVersion":      @"Get ( ApplicationVersion )",
    };
    NSMutableDictionary* out = [NSMutableDictionary dictionary];
    for (NSString* key in probes)
    {
        NSString* v = EvalExpr( env, probes[key] );
        out[key] = v ?: @"?";
    }
    out[@"helper"] = @(kVersionString);

    // wedge diagnostics: a modal dialog or sheet explains dead triggers,
    // callback timeouts, and idleState "unsafe" better than any log
    RunOnMain( ^{
        NSWindow* modal = [NSApp modalWindow];
        out[@"modalWindow"] = modal
            ? (modal.title.length ? modal.title : NSStringFromClass( modal.class ))
            : @"";
        NSMutableArray* sheets = [NSMutableArray array];
        for (NSWindow* w in [NSApp orderedWindows])
            if (w.attachedSheet != nil && w.title.length)
                [sheets addObject:w.title];
        out[@"sheetsOn"] = sheets;
        out[@"keyWindowClass"] = [NSApp keyWindow]
            ? NSStringFromClass( [NSApp keyWindow].class ) : @"";
    } );
    out[@"channelActive"] = @(gChannelActive);
    out[@"channelFolder"] = gChannelFolder ?: @"";
    out[@"channelAutoArmed"] = @(gChannelAutoArmed);
    out[@"hostApp"] = HostAppName();
    return JSONString( out );
}

// ---- script starting --------------------------------------------------------------------

static FMX_ScriptControl ScriptControlFromString( NSString* s )
{
    NSString* c = s.lowercaseString;
    if ([c isEqualToString:@"halt"])   return kFMXT_Halt;
    if ([c isEqualToString:@"exit"])   return kFMXT_Exit;
    if ([c isEqualToString:@"pause"])  return kFMXT_Pause;
    return kFMXT_Resume;
}

static NSString* StartScript( NSString* fileName, NSString* scriptName, NSString* param, NSString* control )
{
    if (fileName.length == 0 || scriptName.length == 0)
        return @"ERROR: fileName and scriptName are required";

    fmx::TextUniquePtr fileT, scriptT;
    AssignFMXText( *fileT, fileName );
    AssignFMXText( *scriptT, scriptName );

    fmx::DataUniquePtr paramD;
    if (param.length)
    {
        fmx::TextUniquePtr paramT;
        AssignFMXText( *paramT, param );
        paramD->SetAsText( *paramT, paramD->GetLocale() );
    }

    const FMX_ErrorCode err = FMX_StartScript( &(*fileT), &(*scriptT),
                                               ScriptControlFromString( control ),
                                               param.length ? &(*paramD) : nullptr );
    if (err != 0)
        return [NSString stringWithFormat:@"ERROR: StartScript failed (%d)", (int)err];
    return [NSString stringWithFormat:@"OK: queued \"%@\" in \"%@\"", scriptName, fileName];
}

// ---- command channel --------------------------------------------------------------------
//
// ADTH_ChannelStart( folder ) arms an idle-loop worker: the agent drops
// <anything>.json command files into the folder; the plug-in executes each and
// writes results/<same-name>, then moves the command to processed/. The channel
// is off until a calc inside FileMaker arms it (typically an OnFirstWindowOpen
// script), so no standing execution surface exists without an opt-in.

static NSString* ChannelStart( NSString* folder )
{
    if (folder.length == 0) return @"ERROR: folder path required";
    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSError* err = nil;
    for (NSString* sub in @[@"", @"results", @"processed"])
    {
        NSString* p = sub.length ? [folder stringByAppendingPathComponent:sub] : folder;
        if (![fmgr createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:&err])
            return [NSString stringWithFormat:@"ERROR: cannot create %@: %@", p, err.localizedDescription];
    }
    gChannelFolder = [folder copy];
    gChannelActive = YES;
    gChannelProcessed = 0;
    gChannelLastError = nil;
    return [NSString stringWithFormat:@"OK: channel armed at %@", folder];
}

static NSString* ChannelStatusJSON( void )
{
    return JSONString( @{
        @"active":    @(gChannelActive),
        @"folder":    gChannelFolder ?: @"",
        @"processed": @(gChannelProcessed),
        @"lastError": gChannelLastError ?: @"",
        @"autoArmed": @(gChannelAutoArmed),
        @"hostApp":   HostAppName(),
        @"helper":    @(kVersionString),
    } );
}

// Auto-arm: consult ~/.adt-helper/config.json on idle and, if it opts in and
// names the frontmost file, arm the channel with no script run. The config
// file's existence + autoArm:true IS the standing consent; without it nothing
// arms. A manual ADTH_ChannelStop records the config mtime so auto-arm stays
// off until the user edits the config again (re-consent) or FileMaker restarts.
static NSString* AutoArmConfigPath( void )
{
    return [NSHomeDirectory() stringByAppendingPathComponent:@".adt-helper/config.json"];
}

// Which FileMaker copy is hosting this plug-in — "FileMaker Pro",
// "FileMaker Pro Agent", … Joe runs duplicated FileMaker apps as independent
// clients, and they SHARE the version-keyed Extensions folder, so one plug-in
// binary is loaded by every copy. Auto-arm is scoped by this name so an
// agent-owned copy can arm itself while the human's copy never does.
static NSString* HostAppName( void )
{
    NSString* p = [[NSBundle mainBundle] bundlePath];
    if (p.length == 0) return [[NSProcessInfo processInfo] processName] ?: @"";
    return [[p lastPathComponent] stringByDeletingPathExtension];
}

static void AutoArmIdleCheck( const fmx::ExprEnv& env )
{
    if (gChannelActive) return;                      // already armed (manually or earlier)

    // throttle: stat the config at most ~every 3s, not every idle tick
    NSTimeInterval now = [NSDate timeIntervalSinceReferenceDate];
    if (now - gAutoArmLastCheck < 3.0) return;
    gAutoArmLastCheck = now;

    NSString* cfgPath = AutoArmConfigPath();
    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSDictionary* attrs = [fmgr attributesOfItemAtPath:cfgPath error:nil];
    if (!attrs) return;                              // no config → no standing consent → nothing arms
    NSTimeInterval cfgMtime = [(NSDate*)attrs[NSFileModificationDate] timeIntervalSinceReferenceDate];

    // a manual stop suppresses auto-arm until the config is touched again
    if (gAutoArmSuppressMtime != 0 && cfgMtime <= gAutoArmSuppressMtime) return;

    NSData* raw = [NSData dataWithContentsOfFile:cfgPath];
    NSDictionary* cfg = raw.length ? [NSJSONSerialization JSONObjectWithData:raw options:0 error:nil] : nil;
    if (![cfg isKindOfClass:[NSDictionary class]]) return;

    // per-app scoping (0.4.1): an "apps" map keyed by the host app's name
    // overrides the top-level keys for THIS copy of FileMaker. A copy with
    // {"autoArm": false} never arms, which is how the human's copy stays out
    // of the agent's way while both share one plug-in binary.
    NSString* host = HostAppName();
    NSDictionary* apps = [cfg[@"apps"] isKindOfClass:[NSDictionary class]] ? cfg[@"apps"] : nil;
    NSDictionary* mine = [apps[host] isKindOfClass:[NSDictionary class]] ? apps[host] : nil;

    id armVal = (mine && mine[@"autoArm"] != nil) ? mine[@"autoArm"] : cfg[@"autoArm"];
    if (![armVal respondsToSelector:@selector(boolValue)] || ![armVal boolValue]) return;

    // which file is frontmost IN THIS PROCESS right now?
    NSString* frontFile = EvalExpr( env, @"Get ( FileName )" );
    if (frontFile.length == 0) return;

    // allowlist: files[] must name it (a "*" entry allows any open file)
    id filesVal = (mine && mine[@"files"] != nil) ? mine[@"files"] : cfg[@"files"];
    NSArray* files = [filesVal isKindOfClass:[NSArray class]] ? filesVal : @[];
    BOOL allowed = NO;
    for (id f in files)
        if ([f isKindOfClass:[NSString class]] && ([f isEqualToString:@"*"] || [f isEqualToString:frontFile]))
            { allowed = YES; break; }
    if (!allowed) return;

    // folder: explicit override wins; otherwise namespace by host app so two
    // copies with the SAME file open never race for one command queue —
    // ~/.adt-helper/<app>/<file>
    id folderVal = (mine && mine[@"folder"] != nil) ? mine[@"folder"] : cfg[@"folder"];
    NSString* folder = [folderVal isKindOfClass:[NSString class]] && [folderVal length]
        ? folderVal
        : [[[NSHomeDirectory() stringByAppendingPathComponent:@".adt-helper"]
                stringByAppendingPathComponent:host]
                stringByAppendingPathComponent:frontFile];

    NSString* r = ChannelStart( folder );
    gChannelAutoArmed = [r hasPrefix:@"OK"];
    if (!gChannelAutoArmed) gChannelLastError = r;
}

// Execute one parsed command; returns a JSON-serializable result dictionary.
static NSDictionary* ExecuteChannelCommand( NSDictionary* cmd, const fmx::ExprEnv& env )
{
    NSString* verb = [cmd[@"cmd"] isKindOfClass:[NSString class]] ? cmd[@"cmd"] : @"";
    NSString* (^S)(NSString*) = ^NSString*( NSString* key ) {
        id v = cmd[key];
        return [v isKindOfClass:[NSString class]] ? v : @"";
    };

    if ([verb isEqualToString:@"version"])
        return @{ @"ok": @YES, @"result": @(kVersionString) };

    if ([verb isEqualToString:@"state"])
        return @{ @"ok": @YES, @"result": StateJSON( env ) };

    if ([verb isEqualToString:@"windowlist"])
    {
        __block NSString* json = @"[]";
        RunOnMain( ^{
            NSMutableArray* arr = [NSMutableArray array];
            for (NSWindow* w in [NSApp orderedWindows])
            {
                if (w.title.length == 0 && !w.isVisible) continue;
                [arr addObject:@{ @"title": w.title ?: @"", @"visible": @(w.isVisible),
                                  @"main": @(w.isMainWindow),
                                  @"sheet": @(w.attachedSheet != nil),
                                  @"class": NSStringFromClass( w.class ),
                                  @"width": @((int)w.frame.size.width),
                                  @"height": @((int)w.frame.size.height) }];
            }
            json = JSONString( arr );
        } );
        return @{ @"ok": @YES, @"result": json };
    }

    if ([verb isEqualToString:@"evaluate"])
    {
        NSString* expr = S( @"expr" );
        if (expr.length == 0) return @{ @"ok": @NO, @"error": @"expr required" };
        NSString* v = EvalExpr( env, expr );
        return v ? @{ @"ok": @YES, @"result": v }
                 : @{ @"ok": @NO, @"error": @"evaluation failed" };
    }

    if ([verb isEqualToString:@"sql"])
    {
        NSString* query = S( @"query" );
        if (query.length == 0) return @{ @"ok": @NO, @"error": @"query required" };
        NSString* file = S( @"file" );
        if (file.length == 0) file = EvalExpr( env, @"Get ( FileName )" ) ?: @"";
        fmx::TextUniquePtr queryT, fileT;
        AssignFMXText( *queryT, query );
        AssignFMXText( *fileT, file );
        fmx::DataVectUniquePtr params;
        fmx::DataUniquePtr result;
        const fmx::errcode err = env.ExecuteFileSQLTextResult( *queryT, *fileT, *params, *result, '\t', '\n' );
        if (err != 0)
            return @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"SQL error %d", (int)err] };
        return @{ @"ok": @YES, @"result": NSStringFromFMXText( result->GetAsText() ) };
    }

    if ([verb isEqualToString:@"runscript"])
    {
        NSString* file = S( @"file" );
        if (file.length == 0) file = EvalExpr( env, @"Get ( FileName )" ) ?: @"";
        NSString* r = StartScript( file, S( @"script" ), S( @"param" ), S( @"control" ) );
        BOOL ok = [r hasPrefix:@"OK"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    if ([verb isEqualToString:@"snapshot"])
    {
        NSString* path = S( @"path" );
        if (path.length == 0) return @{ @"ok": @NO, @"error": @"path required" };
        NSRect region = NSZeroRect;
        if (cmd[@"w"] && cmd[@"h"])
            region = NSMakeRect( [cmd[@"x"] doubleValue], [cmd[@"y"] doubleValue],
                                 [cmd[@"w"] doubleValue], [cmd[@"h"] doubleValue] );
        CGFloat scale = cmd[@"scale"] ? [cmd[@"scale"] doubleValue] : 0;
        NSString* r = SnapshotByTitle( S( @"window" ), region, scale, path );
        BOOL ok = [r hasPrefix:@"OK"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    if ([verb isEqualToString:@"webviewerlist"])
    {
        NSString* r = WebViewerListJSON( S( @"window" ) );
        BOOL ok = ![r hasPrefix:@"ERROR"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    if ([verb isEqualToString:@"help"])
        return @{ @"ok": @YES, @"result": @"version | state | windowlist | webviewerlist {window?} | evaluate {expr} | sql {query, file?} | runscript {script, file?, param?, control?} | snapshot {path, window?, x/y/w/h?, scale?} | websnapshot {path, window?, index?} | clipboard-formats | clipboard-get {code?} | clipboard-set {xml, code?}" };

    if ([verb isEqualToString:@"websnapshot"])
    {
        NSString* path = S( @"path" );
        if (path.length == 0) return @{ @"ok": @NO, @"error": @"path required" };
        NSInteger idx = cmd[@"index"] ? [cmd[@"index"] integerValue] : 0;
        NSString* r = WebViewerSnapshot( S( @"window" ), idx, path );
        BOOL ok = [r hasPrefix:@"OK"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    if ([verb isEqualToString:@"clipboard-formats"])
        return @{ @"ok": @YES, @"result": ClipboardFormatsJSON() };

    if ([verb isEqualToString:@"clipboard-get"])
    {
        NSString* r = ClipboardGetXML( S( @"code" ) );
        BOOL ok = ![r hasPrefix:@"ERROR"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    if ([verb isEqualToString:@"clipboard-set"])
    {
        NSString* xml = S( @"xml" );
        if (xml.length == 0) return @{ @"ok": @NO, @"error": @"xml required" };
        NSString* r = ClipboardSetXML( xml, S( @"code" ) );
        BOOL ok = [r hasPrefix:@"OK"];
        return ok ? @{ @"ok": @YES, @"result": r } : @{ @"ok": @NO, @"error": r };
    }

    return @{ @"ok": @NO,
              @"error": [NSString stringWithFormat:@"unknown cmd \"%@\" (version, state, windowlist, webviewerlist, evaluate, sql, runscript, snapshot, websnapshot, clipboard-formats, clipboard-get, clipboard-set, help)", verb] };
}

static void ChannelIdleTick( void )
{
    // A channel whose folder has been deleted out from under it is DEAD, not
    // armed: without this the plug-in keeps gChannelActive forever, reads an
    // unreadable folder every tick, and auto-arm never fires again (0.4.0 bug,
    // hit live 2026-08-29 by removing a channel folder during a test).
    if (gChannelActive && gChannelFolder.length > 0)
    {
        BOOL isDir = NO;
        if (![[NSFileManager defaultManager] fileExistsAtPath:gChannelFolder isDirectory:&isDir] || !isDir)
        {
            gChannelActive = NO;
            gChannelAutoArmed = NO;
            gChannelLastError = @"channel folder disappeared — disarmed";
        }
    }

    if (!gChannelActive || gChannelFolder.length == 0)
    {
        // not armed — see whether the auto-arm config wants us to be.
        // needs an env (to read Get(FileName)); build one just as the
        // command loop below does.
        if (!gChannelActive)
        {
            fmx::ExprEnvUniquePtr aenv;
            FMX_SetToCurrentEnv( &(*aenv) );
            AutoArmIdleCheck( *aenv );
        }
        if (!gChannelActive || gChannelFolder.length == 0) return;
    }

    NSFileManager* fmgr = [NSFileManager defaultManager];
    NSArray<NSString*>* entries = [fmgr contentsOfDirectoryAtPath:gChannelFolder error:nil];
    if (entries.count == 0) return;

    NSMutableArray<NSString*>* commands = [NSMutableArray array];
    for (NSString* name in [entries sortedArrayUsingSelector:@selector(compare:)])
    {
        if ([name hasPrefix:@"."]) continue;
        if (![name.pathExtension isEqualToString:@"json"]) continue;
        [commands addObject:name];
        if (commands.count >= 5) break;   // bound the work per idle tick
    }
    if (commands.count == 0) return;

    // one environment for the whole tick
    fmx::ExprEnvUniquePtr env;
    FMX_SetToCurrentEnv( &(*env) );

    for (NSString* name in commands)
    {
        NSString* cmdPath = [gChannelFolder stringByAppendingPathComponent:name];
        NSData* raw = [NSData dataWithContentsOfFile:cmdPath];
        NSError* jerr = nil;
        NSDictionary* cmd = raw.length
            ? [NSJSONSerialization JSONObjectWithData:raw options:0 error:&jerr] : nil;

        NSDictionary* result;
        if (![cmd isKindOfClass:[NSDictionary class]])
        {
            result = @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"bad command file: %@",
                        jerr.localizedDescription ?: @"not a JSON object"] };
        }
        else
        {
            @try       { result = ExecuteChannelCommand( cmd, *env ); }
            @catch (NSException* ex)
            {
                result = @{ @"ok": @NO, @"error": [NSString stringWithFormat:@"exception: %@", ex.reason] };
            }
        }

        NSMutableDictionary* full = [result mutableCopy];
        full[@"command"] = name;
        NSData* out = [NSJSONSerialization dataWithJSONObject:full options:NSJSONWritingPrettyPrinted error:nil];
        NSString* resultPath = [[gChannelFolder stringByAppendingPathComponent:@"results"]
                                    stringByAppendingPathComponent:name];
        [out writeToFile:resultPath options:NSDataWritingAtomic error:nil];

        NSString* donePath = [[gChannelFolder stringByAppendingPathComponent:@"processed"]
                                    stringByAppendingPathComponent:name];
        [fmgr removeItemAtPath:donePath error:nil];
        NSError* merr = nil;
        if (![fmgr moveItemAtPath:cmdPath toPath:donePath error:&merr])
        {
            gChannelLastError = merr.localizedDescription;
            [fmgr removeItemAtPath:cmdPath error:nil];   // never reprocess
        }
        gChannelProcessed++;
    }
}

// ---- calc function entry points ---------------------------------------------------------

static FMX_PROC(fmx::errcode) Do_ADTH_Version( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, @(kVersionString) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_WindowList( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    __block NSString* json = @"[]";
    RunOnMain( ^{
        NSMutableArray* arr = [NSMutableArray array];
        for (NSWindow* w in [NSApp orderedWindows])
        {
            if (w.title.length == 0 && !w.isVisible) continue;
            [arr addObject:@{
                @"title":    w.title ?: @"",
                @"visible":  @(w.isVisible),
                @"main":     @(w.isMainWindow),
                @"key":      @(w.isKeyWindow),
                @"miniaturized": @(w.isMiniaturized),
                @"sheet":    @(w.attachedSheet != nil),
                @"class":    NSStringFromClass( w.class ),
                @"width":    @((int)w.frame.size.width),
                @"height":   @((int)w.frame.size.height),
            }];
        }
        json = JSONString( arr );
    } );
    SetTextResult( results, json );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_WindowSnapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* title = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    SetTextResult( results, SnapshotByTitle( title, NSZeroRect, 0, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_Snapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );

    NSString* window = @"";
    NSRect region = NSZeroRect;
    CGFloat scale = 0;
    if (dataVect.Size() >= 2)
    {
        NSString* optsStr = NSStringFromFMXText( dataVect.At( 1 ).GetAsText() );
        NSDictionary* opts = optsStr.length
            ? [NSJSONSerialization JSONObjectWithData:[optsStr dataUsingEncoding:NSUTF8StringEncoding]
                                              options:0 error:nil] : nil;
        if (![opts isKindOfClass:[NSDictionary class]] && optsStr.length)
        {
            SetTextResult( results, @"ERROR: options must be a JSON object, e.g. {\"window\":\"Contacts\",\"scale\":1}" );
            return 0;
        }
        if ([opts[@"window"] isKindOfClass:[NSString class]]) window = opts[@"window"];
        if (opts[@"w"] && opts[@"h"])
            region = NSMakeRect( [opts[@"x"] doubleValue], [opts[@"y"] doubleValue],
                                 [opts[@"w"] doubleValue], [opts[@"h"] doubleValue] );
        if (opts[@"scale"]) scale = [opts[@"scale"] doubleValue];
    }
    SetTextResult( results, SnapshotByTitle( window, region, scale, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_WebViewerSnapshot( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: path parameter required" ); return 0; }
    NSString* path  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* title = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    NSInteger idx   = (dataVect.Size() >= 3) ? (NSInteger)dataVect.At( 2 ).GetAsNumber().AsLong() : 0;
    SetTextResult( results, WebViewerSnapshot( title, idx, path ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_WebViewerList( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    NSString* title = (dataVect.Size() >= 1) ? NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) : @"";
    SetTextResult( results, WebViewerListJSON( title ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_State( short, const fmx::ExprEnv& env, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, StateJSON( env ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_RunScript( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 2) { SetTextResult( results, @"ERROR: fileName and scriptName required" ); return 0; }
    NSString* file    = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* script  = NSStringFromFMXText( dataVect.At( 1 ).GetAsText() );
    NSString* param   = (dataVect.Size() >= 3) ? NSStringFromFMXText( dataVect.At( 2 ).GetAsText() ) : @"";
    NSString* control = (dataVect.Size() >= 4) ? NSStringFromFMXText( dataVect.At( 3 ).GetAsText() ) : @"";
    SetTextResult( results, StartScript( file, script, param, control ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ClipboardFormats( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, ClipboardFormatsJSON() );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ClipboardGetXML( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    NSString* code = (dataVect.Size() >= 1) ? NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) : @"";
    SetTextResult( results, ClipboardGetXML( code ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ClipboardSetXML( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: xml parameter required" ); return 0; }
    NSString* xml  = NSStringFromFMXText( dataVect.At( 0 ).GetAsText() );
    NSString* code = (dataVect.Size() >= 2) ? NSStringFromFMXText( dataVect.At( 1 ).GetAsText() ) : @"";
    SetTextResult( results, ClipboardSetXML( xml, code ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ChannelStart( short, const fmx::ExprEnv&, const fmx::DataVect& dataVect, fmx::Data& results )
{
    if (dataVect.Size() < 1) { SetTextResult( results, @"ERROR: folder parameter required" ); return 0; }
    SetTextResult( results, ChannelStart( NSStringFromFMXText( dataVect.At( 0 ).GetAsText() ) ) );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ChannelStop( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    gChannelActive = NO;
    gChannelAutoArmed = NO;
    // suppress auto-arm until the config file is edited again (or FileMaker
    // restarts): record the current config mtime as the suppression floor.
    NSDictionary* attrs = [[NSFileManager defaultManager] attributesOfItemAtPath:AutoArmConfigPath() error:nil];
    gAutoArmSuppressMtime = attrs
        ? [(NSDate*)attrs[NSFileModificationDate] timeIntervalSinceReferenceDate]
        : [NSDate timeIntervalSinceReferenceDate];
    SetTextResult( results, @"OK: channel stopped" );
    return 0;
}

static FMX_PROC(fmx::errcode) Do_ADTH_ChannelStatus( short, const fmx::ExprEnv&, const fmx::DataVect&, fmx::Data& results )
{
    SetTextResult( results, ChannelStatusJSON() );
    return 0;
}

// ---- registration -----------------------------------------------------------------------

struct FuncDef { short id; const char* name; const char* definition; const char* description;
                 fmx::uint32 minArgs; fmx::uint32 maxArgs; fmx::ExtPluginType func; };

static const FuncDef kFuncs[] = {
    { kADTH_VersionID,           "ADTH_Version",            "ADTH_Version",
      "Returns the ADT Helper plug-in version", 0, 0, Do_ADTH_Version },
    { kADTH_WindowListID,        "ADTH_WindowList",         "ADTH_WindowList",
      "Returns a JSON array describing FileMaker's open windows", 0, 0, Do_ADTH_WindowList },
    { kADTH_WindowSnapshotID,    "ADTH_WindowSnapshot",     "ADTH_WindowSnapshot( path { ; windowTitle } )",
      "Writes a PNG of a FileMaker window's content to path; frontmost titled window when no title given", 1, 2, Do_ADTH_WindowSnapshot },
    { kADTH_SnapshotID,          "ADTH_Snapshot",           "ADTH_Snapshot( path { ; optionsJSON } )",
      "Window snapshot with JSON options: window (title match), x/y/w/h region in points, scale", 1, 2, Do_ADTH_Snapshot },
    { kADTH_WebViewerSnapshotID, "ADTH_WebViewerSnapshot",  "ADTH_WebViewerSnapshot( path { ; windowTitle ; index } )",
      "Writes a PNG of a web viewer's rendered content (WKWebView snapshot)", 1, 3, Do_ADTH_WebViewerSnapshot },
    { kADTH_WebViewerListID,     "ADTH_WebViewerList",      "ADTH_WebViewerList( { windowTitle } )",
      "Returns JSON of a window's web viewers: index, url, size, loading", 0, 1, Do_ADTH_WebViewerList },
    { kADTH_StateID,             "ADTH_State",              "ADTH_State",
      "Returns JSON of the current context: file, layout, mode, found count, errors, modal-dialog/sheet wedge diagnostics, channel state", 0, 0, Do_ADTH_State },
    { kADTH_RunScriptID,         "ADTH_RunScript",          "ADTH_RunScript( fileName ; scriptName { ; parameter ; control } )",
      "Queues a FileMaker script; control: resume (default), halt, exit, pause", 2, 4, Do_ADTH_RunScript },
    { kADTH_ClipboardFormatsID,  "ADTH_ClipboardFormats",   "ADTH_ClipboardFormats",
      "Returns JSON of clipboard flavors, flagging FileMaker XML types", 0, 0, Do_ADTH_ClipboardFormats },
    { kADTH_ClipboardGetXMLID,   "ADTH_ClipboardGetXML",    "ADTH_ClipboardGetXML( { fmCode } )",
      "Returns FileMaker XML from the clipboard (XMSS, XMSC, XML2, XMTB, XMFD, XMVL, XMFN)", 0, 1, Do_ADTH_ClipboardGetXML },
    { kADTH_ClipboardSetXMLID,   "ADTH_ClipboardSetXML",    "ADTH_ClipboardSetXML( xml { ; fmCode } )",
      "Puts FileMaker XML onto the clipboard; flavor inferred from the XML when no code given", 1, 2, Do_ADTH_ClipboardSetXML },
    { kADTH_ChannelStartID,      "ADTH_ChannelStart",       "ADTH_ChannelStart( folder )",
      "Arms the drop-folder command channel: <folder>/*.json commands run on idle, results in <folder>/results", 1, 1, Do_ADTH_ChannelStart },
    { kADTH_ChannelStopID,       "ADTH_ChannelStop",        "ADTH_ChannelStop",
      "Disarms the command channel", 0, 0, Do_ADTH_ChannelStop },
    { kADTH_ChannelStatusID,     "ADTH_ChannelStatus",      "ADTH_ChannelStatus",
      "Returns JSON channel status: active, folder, processed count, last error", 0, 0, Do_ADTH_ChannelStatus },
};

static fmx::ptrtype Do_PluginInit( fmx::int16 version )
{
    fmx::ptrtype result( static_cast<fmx::ptrtype>(kDoNotEnable) );
    const fmx::QuadCharUniquePtr pluginID( kADTh[0], kADTh[1], kADTh[2], kADTh[3] );
    fmx::uint32 flags( fmx::ExprEnv::kDisplayInAllDialogs | fmx::ExprEnv::kFutureCompatible );

    if (version >= k150ExtnVersion)
    {
        bool allOK = true;
        for (const FuncDef& f : kFuncs)
        {
            fmx::TextUniquePtr name, definition, description;
            name->Assign( f.name, fmx::Text::kEncoding_UTF8 );
            definition->Assign( f.definition, fmx::Text::kEncoding_UTF8 );
            description->Assign( f.description, fmx::Text::kEncoding_UTF8 );
            if (fmx::ExprEnv::RegisterExternalFunctionEx( *pluginID, f.id, *name, *definition, *description,
                                                          f.minArgs, f.maxArgs, flags, f.func ) != 0)
            {
                allOK = false;
            }
        }
        if (allOK) result = kCurrentExtnVersion;
    }
    return result;
}

static void Do_PluginShutdown( fmx::int16 version )
{
    const fmx::QuadCharUniquePtr pluginID( kADTh[0], kADTh[1], kADTh[2], kADTh[3] );
    if (version >= k140ExtnVersion)
    {
        for (const FuncDef& f : kFuncs)
            static_cast<void>(fmx::ExprEnv::UnRegisterExternalFunction( *pluginID, f.id ));
    }
}

// ---- boilerplate ------------------------------------------------------------------------

static void CopyUTF8StrToUnichar16Str( const char* inStr, fmx::uint32 outStrSize, fmx::unichar16* outStr )
{
    fmx::TextUniquePtr txt;
    txt->Assign( inStr, fmx::Text::kEncoding_UTF8 );
    const fmx::uint32 txtSize( (outStrSize <= txt->GetSize()) ? (outStrSize - 1) : txt->GetSize() );
    txt->GetUnicode( outStr, 0, txtSize );
    outStr[txtSize] = 0;
}

static void Do_GetString( fmx::uint32 whichString, fmx::uint32, fmx::uint32 outBufferSize, fmx::unichar16* outBuffer )
{
    switch (whichString)
    {
        case kFMXT_NameStr:
            CopyUTF8StrToUnichar16Str( "ADT Helper", outBufferSize, outBuffer );
            break;
        case kFMXT_AppConfigStr:
            CopyUTF8StrToUnichar16Str( "Agent helpers: snapshots, state probes, script starting, XML clipboard, drop-folder command channel", outBufferSize, outBuffer );
            break;
        case kFMXT_OptionsStr:
            CopyUTF8StrToUnichar16Str( kADTh, outBufferSize, outBuffer );
            outBuffer[4] = '1';   // always "1"
            outBuffer[5] = 'n';   // no Configure button
            outBuffer[6] = 'n';   // always "n"
            outBuffer[7] = 'Y';   // wants Init/Shutdown
            outBuffer[8] = 'Y';   // wants Idle (command channel)
            outBuffer[9] = 'n';   // no session/file shutdown messages
            outBuffer[10] = 'n';  // always "n"
            outBuffer[11] = 0;
            break;
        default:
            outBuffer[0] = 0;
            break;
    }
}

FMX_ExternCallPtr gFMX_ExternCallPtr( nullptr );

void FMX_ENTRYPT FMExternCallProc( FMX_ExternCallPtr pb )
{
    gFMX_ExternCallPtr = pb;
    switch (pb->whichCall)
    {
        case kFMXT_Init:
            pb->result = Do_PluginInit( pb->extnVersion );
            break;
        case kFMXT_Idle:
            if (!pb->unsafeCalls && pb->parm1 != kFMXT_Unsafe)
                ChannelIdleTick();
            break;
        case kFMXT_Shutdown:
            Do_PluginShutdown( pb->extnVersion );
            break;
        case kFMXT_GetString:
            Do_GetString( static_cast<fmx::uint32>(pb->parm1), static_cast<fmx::uint32>(pb->parm2),
                          static_cast<fmx::uint32>(pb->parm3), reinterpret_cast<fmx::unichar16*>(pb->result) );
            break;
        default:
            break;
    }
}
