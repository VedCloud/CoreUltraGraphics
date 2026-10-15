// CPU-only luminance capture. No Metal/CoreImage renderer or recording upload.
#import <Foundation/Foundation.h>
#import <AVFoundation/AVFoundation.h>
#import <CoreVideo/CoreVideo.h>
#import <ImageIO/ImageIO.h>
#import <ApplicationServices/ApplicationServices.h>

@interface LatitudeCameraSink : NSObject <AVCaptureVideoDataOutputSampleBufferDelegate>
@property NSString *outputPath;
@property(atomic) BOOL completed;
@property(atomic) BOOL saved;
@property unsigned receivedFrames;
@end

@implementation LatitudeCameraSink
- (void)captureOutput:(AVCaptureOutput *)output didOutputSampleBuffer:(CMSampleBufferRef)sample
       fromConnection:(AVCaptureConnection *)connection {
    if (self.completed) return;
    // Allow auto-exposure to settle before saving the diagnostic frame.
    if (++self.receivedFrames < 30) return;
    CVPixelBufferRef pixels = CMSampleBufferGetImageBuffer(sample);
    if (!pixels || CVPixelBufferGetPixelFormatType(pixels) != kCVPixelFormatType_422YpCbCr8_yuvs) {
        fprintf(stderr, "No native YUY2 pixel buffer; format conversion was not attempted.\n");
        self.completed = YES; return;
    }
    if (CVPixelBufferLockBaseAddress(pixels, kCVPixelBufferLock_ReadOnly) != kCVReturnSuccess) return;
    size_t width=CVPixelBufferGetWidth(pixels), height=CVPixelBufferGetHeight(pixels);
    size_t stride=CVPixelBufferGetBytesPerRow(pixels);
    const uint8_t *base=CVPixelBufferGetBaseAddress(pixels);
    if (!base || width==0 || height==0 || width>4096 || height>4096 || stride<width*2) {
        CVPixelBufferUnlockBaseAddress(pixels,kCVPixelBufferLock_ReadOnly);
        self.completed=YES; return;
    }
    NSMutableData *gray=[NSMutableData dataWithLength:width*height];
    uint8_t *target=gray.mutableBytes;
    double sum=0,squares=0; unsigned low=255,high=0;
    for (size_t y=0;y<height;y++) for(size_t x=0;x<width;x++) {
        unsigned value=base[y*stride+x*2]; // YUY2: Y0 U Y1 V.
        target[y*width+x]=value; sum+=value; squares+=value*value;
        if(value<low)low=value; if(value>high)high=value;
    }
    CVPixelBufferUnlockBaseAddress(pixels,kCVPixelBufferLock_ReadOnly);
    double count=width*height,mean=sum/count,variance=squares/count-mean*mean;
    printf("Delivered CPU-readable frame: %zux%zu, luma min=%u max=%u mean=%.2f variance=%.2f\n",
           width,height,low,high,mean,variance);
    CGColorSpaceRef space=CGColorSpaceCreateDeviceGray();
    CGDataProviderRef provider=CGDataProviderCreateWithCFData((__bridge CFDataRef)gray);
    CGImageRef image=CGImageCreate(width,height,8,8,width,space,kCGImageAlphaNone,provider,NULL,false,kCGRenderingIntentDefault);
    NSURL *url=[NSURL fileURLWithPath:self.outputPath];
    CGImageDestinationRef dest=CGImageDestinationCreateWithURL((__bridge CFURLRef)url,CFSTR("public.png"),1,NULL);
    if(image && dest) { CGImageDestinationAddImage(dest,image,NULL); self.saved=CGImageDestinationFinalize(dest); }
    if(dest)CFRelease(dest); if(image)CGImageRelease(image);
    if(provider)CGDataProviderRelease(provider); if(space)CGColorSpaceRelease(space);
    printf("Image save: %s\n",self.saved?self.outputPath.UTF8String:"failed");
    self.completed=YES;
}
@end

int main(int argc,const char *argv[]) { @autoreleasepool {
    if(argc!=2) { fprintf(stderr,"Usage: CameraProbe /path/to/local-camera-test.png\nOnly captures after macOS camera permission; saves one private grayscale frame locally.\n"); return 2; }
    __block BOOL answered=NO,allowed=NO;
    AVAuthorizationStatus status=[AVCaptureDevice authorizationStatusForMediaType:AVMediaTypeVideo];
    if(status==AVAuthorizationStatusAuthorized) {answered=YES;allowed=YES;}
    else if(status==AVAuthorizationStatusNotDetermined)
        [AVCaptureDevice requestAccessForMediaType:AVMediaTypeVideo completionHandler:^(BOOL granted){allowed=granted;answered=YES;}];
    else answered=YES;
    NSDate *deadline=[NSDate dateWithTimeIntervalSinceNow:60];
    while(!answered && deadline.timeIntervalSinceNow>0)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
    if(!allowed) {fprintf(stderr,"Camera permission unavailable/denied. Run as your normal desktop user and allow camera access.\n");return 3;}
    AVCaptureDeviceDiscoverySession *discovery=[AVCaptureDeviceDiscoverySession
        discoverySessionWithDeviceTypes:@[AVCaptureDeviceTypeExternalUnknown,AVCaptureDeviceTypeBuiltInWideAngleCamera]
        mediaType:AVMediaTypeVideo position:AVCaptureDevicePositionUnspecified];
    AVCaptureDevice *device=nil;
    for(AVCaptureDevice *candidate in discovery.devices) {
        printf("Camera: %s [%s]\n",candidate.localizedName.UTF8String,candidate.uniqueID.UTF8String);
        if([candidate.localizedName containsString:@"Integrated"])device=candidate;
    }
    if(!device) {fprintf(stderr,"Integrated camera not found; no substitute device selected.\n");return 4;}
    NSError *error=nil;
    AVCaptureDeviceInput *input=[AVCaptureDeviceInput deviceInputWithDevice:device error:&error];
    if(!input) {fprintf(stderr,"Input error: %s\n",error.description.UTF8String);return 5;}
    AVCaptureSession *session=[AVCaptureSession new];
    if(![session canSetSessionPreset:AVCaptureSessionPreset640x480])return 6;
    session.sessionPreset=AVCaptureSessionPreset640x480;
    if(![session canAddInput:input])return 7; [session addInput:input];
    AVCaptureVideoDataOutput *output=[AVCaptureVideoDataOutput new];
    output.alwaysDiscardsLateVideoFrames=YES;
    output.videoSettings=@{(id)kCVPixelBufferPixelFormatTypeKey:@(kCVPixelFormatType_422YpCbCr8_yuvs)};
    LatitudeCameraSink *sink=[LatitudeCameraSink new]; sink.outputPath=[NSString stringWithUTF8String:argv[1]];
    [output setSampleBufferDelegate:sink queue:dispatch_queue_create("LatitudeCameraCPU",DISPATCH_QUEUE_SERIAL)];
    if(![session canAddOutput:output])return 8; [session addOutput:output];
    [session startRunning]; deadline=[NSDate dateWithTimeIntervalSinceNow:15];
    while(!sink.completed && deadline.timeIntervalSinceNow>0)
        [[NSRunLoop currentRunLoop] runUntilDate:[NSDate dateWithTimeIntervalSinceNow:0.1]];
    [session stopRunning];
    if(!sink.completed)fprintf(stderr,"No frame delivered within15seconds. Camera capture/stream startup needs investigation.\n");
    return sink.saved?0:9;
} }
